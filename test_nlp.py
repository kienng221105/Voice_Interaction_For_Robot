import asyncio
import json
import websockets

async def test():
    async with websockets.connect('ws://localhost:8765') as ws:
        await ws.send(b'\x00' * 16000)
        await ws.send(json.dumps({'type': 'audio_end'}))
        print("Waiting for recv 1...")
        print(await ws.recv())
        print("Waiting for recv 2...")
        print(await ws.recv())

asyncio.run(test())
