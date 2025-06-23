import discord

class SimplePaginator(discord.ui.View):
    def __init__(self, pages, page_size=25, title=None, line_builder=None, color=discord.Color.blurple(), timeout=120):
        super().__init__(timeout=timeout)
        self.pages = [pages[i:i+page_size] for i in range(0, len(pages), page_size)]
        self.page = 0
        self.max_page = len(self.pages) - 1
        self.message = None
        self.title = title or "Paginated List"
        self.line_builder = line_builder or (lambda i, item: f"{i+1+self.page*page_size}. {item}")
        self.color = color
        self.page_size = page_size
    async def update_embed(self, interaction=None):
        self.refresh_page_label()
        lines = [self.line_builder(i, item) for i, item in enumerate(self.pages[self.page])]
        embed = discord.Embed(
            title=self.title,
            description='\n'.join(lines) or 'None',
            color=self.color
        )
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.message.edit(embed=embed, view=self)
    @discord.ui.button(emoji='⬅️', style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        else:
            self.page = self.max_page
        await self.update_embed(interaction)
    @discord.ui.button(label='Page', style=discord.ButtonStyle.secondary, disabled=True)
    async def page_display(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass
    @discord.ui.button(emoji='➡️', style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_page:
            self.page += 1
        else:
            self.page = 0
        await self.update_embed(interaction)
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass  # Message was deleted, nothing to update
    def refresh_page_label(self):
        self.children[1].label = f"Page {self.page+1}/{self.max_page+1}"
    async def send(self, channel):
        self.refresh_page_label()
        lines = [self.line_builder(i, item) for i, item in enumerate(self.pages[self.page])]
        embed = discord.Embed(
            title=self.title,
            description='\n'.join(lines) or 'None',
            color=self.color
        )
        self.message = await channel.send(embed=embed, view=self)
