class ApiAccessCog:
    def __init__(self, bot):
        self.bot = bot

    async def fetch_data_from_api(self, api_url):
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                return await response.json()

    @commands.command(name='getdata')
    async def get_data(self, ctx, api_url: str):
        """Fetch data from a specified API URL."""
        data = await self.fetch_data_from_api(api_url)
        await ctx.send(f"Data fetched: {data}")