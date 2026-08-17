import httpx
import asyncio

async def test_fetch():
    url = "https://obscure-space-memory-gx5q9p6r764v39wrr-8080.app.github.dev/job/mini_demo_pipeline/3/consoleText"

    # Using your correct username "Ayub" and your generated API token
    async with httpx.AsyncClient() as client:
        response = await client.get(url, auth=("Ayub", "117b6ee28ebb1a1fcb55f0701cd64e434c"))
        print("Status Code:", response.status_code)
        print("Log Text:\n", response.text[:500]) # Prints the first 500 characters of build #3's log

asyncio.run(test_fetch())