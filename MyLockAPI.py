"""
Parts of this code were generated with the assistance of the GPT language model.
The use of GPT does not affect the license under which this code is offered,
which is MIT Licesing.
"""

import nest_asyncio
import asyncio
import time
import logging
import httpx

from aiohttp import web

#logging class
class GenericLogging:
    def __init__(self, name, log_file):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

#print class
class PrintMsg():
    def __init__(self, b_print=False):
        self.b_print = b_print

    def Print(self, msg):
        if self.b_print:
            print(msg)

#print class instance
MyPrint = PrintMsg(False)

#log class instance
log = GenericLogging(__name__, 'MyLockAPI.log') 

class LockAPIClient:
    """
    A client for the Lock API that provides methods for creating and managing locks.

    Parameters:
        api_key (str): The API key used to authenticate requests to the Lock API.

    Attributes:
        api_key (str): The API key used to authenticate requests to the Lock API.
        base_url (str): The base URL of the Lock API.
        session (requests.Session): The requests session object used to make API requests.

    Raises:
        ValueError: If `api_key` is not a string or is an empty string.

    Example usage:

        # Create a LockAPIClient instance
        client = LockAPIClient(api_key='my_api_key')

        # Create a lock
        lock_id = client.create_lock(name='My Lock')

        # Acquire a lock
        lock_token = client.acquire_lock(lock_id)

        # Release a lock
        client.release_lock(lock_id, lock_token)
    """
    def __init__(self, host='localhost', port=8075):
        self.host = host
        self.port = port
        self.session = None
        self.control = False

    def __enter__(self):
        if not self.control:
            if self.session is None:
                self.start_session()

            while True:
                try:
                    response = self.acquire_lock()
                except httpx.TimeoutException as e:
                    print(f'TimeoutException: {e}')
                    time.sleep(1)
                else:
                    break

            MyPrint.Print(response.json())

    def __exit__(self, exc_type, exc, tb):
        if not self.control:
            while True:
                try:
                    response = self.release_lock()
                except httpx.TimeoutException as e:
                    print(f'TimeoutException: {e}')
                    time.sleep(1)
                else:
                    break

            MyPrint.Print(response.json())

            self.close_session()

    async def __aenter__(self):
        if not self.control:
            if self.session is None:
                self.start_session()

            while True:
                try:
                    response = await self.acquire_lock_async()
                except httpx.TimeoutException as e:
                    print(f'TimeoutException: {e}')
                    await asyncio.sleep(1)
                else:
                    break

            MyPrint.Print(response.json())

    async def __aexit__(self, exc_type, exc, tb):
        if not self.control:
            while True:
                try:
                    response = await self.release_lock_async()
                except httpx.TimeoutException as e:
                    print(f'TimeoutException: {e}')
                    await asyncio.sleep(1)
                else:
                    break

            MyPrint.Print(response.json())

            self.close_session()

    def start_session(self):
        """Starts a new httpx session"""
        self.session = httpx.Client()

    def close_session(self):
        """Closes the httpx session"""
        if self.session is not None:
            self.session.close()
            self.session = None

    def acquire_lock(self):
        """Acquires the lock synchronously"""
        url = f'http://{self.host}:{self.port}/lock'
        response = self.session.post(url, timeout=10)
        if response.status_code != 200:
            raise LockAPIError(f"Failed to acquire lock. Server returned {response.status_code}")
        return response

    def release_lock(self):
        """Releases the lock synchronously"""
        url = f'http://{self.host}:{self.port}/lock'
        response = self.session.delete(url, timeout=10)
        if response.status_code != 200:
            raise LockAPIError(f"Failed to release lock. Server returned {response.status_code}")
        return response

    async def acquire_lock_async(self):
        """Acquires the lock asynchronously"""
        url = f'http://{self.host}:{self.port}/lock'
        response = self.session.post(url, timeout=10)
        if response.status_code != 200:
            raise LockAPIError(f"Failed to acquire lock. Server returned {response.status_code}")
        return response

    async def release_lock_async(self):
        """Releases the lock asynchronously"""
        url = f'http://{self.host}:{self.port}/lock'
        response = self.session.delete(url, timeout=10)
        if response.status_code != 200:
            raise LockAPIError(f"Failed to release lock. Server returned {response.status_code}")
        return response
    
class LockAPIError(Exception):
    pass

class LockAPIServer:
    """
    A server class for managing locks using a REST API.

    :param host: The hostname or IP address to bind the server to. Default is 'localhost'.
    :type host: str
    :param port: The port number to bind the server to. Default is 8000.
    :type port: int
    :param max_locks: The maximum number of locks that can be created. Default is 10.
    :type max_locks: int
    :param lock_timeout: The default timeout for locks, in seconds. Default is 60.
    :type lock_timeout: int

    Example Usage:

    >>> server = LockAPIServer()
    >>> server.start()
    Starting server on localhost:8000
    ...
    >>> # Make a request to create a lock
    >>> response = requests.post('http://localhost:8000/lock', json={'name': 'my_lock'})
    >>> response.json()
    {'name': 'my_lock', 'id': 1, 'locked': False, 'timeout': 60}
    >>> # Make a request to acquire the lock
    >>> response = requests.put('http://localhost:8000/lock/1/acquire', json={'timeout': 30})
    >>> response.json()
    {'name': 'my_lock', 'id': 1, 'locked': True, 'timeout': 30}
    >>> # Make a request to release the lock
    >>> response = requests.put('http://localhost:8000/lock/1/release')
    >>> response.json()
    {'name': 'my_lock', 'id': 1, 'locked': False, 'timeout': 30}
    """
    def __init__(self, port=8075, time_limit=60):

        self.lock = asyncio.Lock()
        self.app = web.Application()
        self.app.add_routes([web.post('/lock', self.acquire_lock),
                             web.delete('/lock', self.release_lock)])
        self.runner = None
        self.port=port
        self.schedule=None
        self.time_limit=time_limit

    async def acquire_lock(self, request):
        """Handler for acquiring the lock"""
        await self.lock.acquire()
        self.schedule=asyncio.create_task(self.schedule_release())

        return web.json_response({'status': self.lock.locked()})

    async def schedule_release(self):
        """Release the lock after 1 minute"""
        await asyncio.sleep(self.time_limit)

        if self.lock.locked:
            self.lock.release()

    async def release_lock(self, request):
        """Handler for releasing the lock"""
        self.lock.release()

        if not self.schedule.done():
            self.schedule.cancel()

        return web.json_response({'status': self.lock.locked()})
    
    async def start(self):
        """Starts the aiohttp server"""
        while True:
            try:
                self.runner = web.AppRunner(self.app)
                await self.runner.setup()
                site = web.TCPSite(self.runner, 'localhost', self.port)
                await site.start()
                print('Lock API Server Started')
            except OSError:
                await asyncio.sleep(1)
    
    async def stop(self):
        """Stops the aiohttp server"""
        if self.runner is not None:
            await self.runner.cleanup()

        if self.lock.locked:
            self.lock.release()

        if not self.schedule.done():
            self.schedule.cancel()

async def main():
    api_server = LockAPIServer()
    await api_server.start()
    
    """
    async with LockAPI() as api_client:
        await api_client.acquire_lock()
        # do some work here
        await api_client.release_lock()"""
    
    #await api_server.stop()

if __name__ == '__main__':
    nest_asyncio.apply()
    asyncio.run(main())