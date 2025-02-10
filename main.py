import discord
from discord.ext import commands
import sqlite3
from datetime import datetime
import asyncio

class ActivityTracker(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.members = True
        intents.guilds = True
        intents.presences = True
        
        super().__init__(command_prefix='!', intents=intents)
        
        # Initialize database
        self.db = sqlite3.connect('activity_tracker.db')
        cursor = self.db.cursor()
        cursor.execute('DROP TABLE IF EXISTS activity_stats')
        self.setup_database()
        
        # Track voice channel join times
        self.voice_join_times = {}
        
    def setup_database(self):
        cursor = self.db.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_stats (
            user_id INTEGER,
            guild_id INTEGER,
            message_count INTEGER DEFAULT 0,
            voice_time INTEGER DEFAULT 0,
            last_updated TIMESTAMP,
            PRIMARY KEY (user_id, guild_id)
        )
        ''')
        self.db.commit()

    async def setup_hook(self):
        # Move stats command registration here
        @self.command(name='stats')
        async def stats(ctx, member: discord.Member = None):
            """Display activity statistics for a user"""
            try:
                if member is None:
                    member = ctx.author

                cursor = self.db.cursor()
                cursor.execute('''
                SELECT message_count, voice_time
                FROM activity_stats
                WHERE user_id = ? AND guild_id = ?
                ''', (member.id, ctx.guild.id))
                
                result = cursor.fetchone()
                if result:
                    message_count, voice_time = result
                    hours = voice_time // 3600
                    minutes = (voice_time % 3600) // 60
                    
                    embed = discord.Embed(
                        title=f"Activity Stats for {member.display_name}",
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="Messages Sent", value=str(message_count))
                    embed.add_field(name="Voice Time", 
                                  value=f"{hours} hours, {minutes} minutes")
                    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
                    await ctx.send(embed=embed)
                else:
                    await ctx.send(f"No activity recorded for {member.display_name} yet.")
            except Exception as e:
                await ctx.send(f"An error occurred while fetching stats: {str(e)}")
    
    async def on_message(self, message):
        if message.author.bot:
            return
            
        # Update message count
        cursor = self.db.cursor()
        cursor.execute('''
        INSERT INTO activity_stats (user_id, guild_id, message_count, last_updated)
        VALUES (?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, guild_id) 
        DO UPDATE SET
            message_count = message_count + 1,
            last_updated = CURRENT_TIMESTAMP
        ''', (message.author.id, message.guild.id))
        self.db.commit()
        
        await self.process_commands(message)
        
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
            
        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            self.voice_join_times[(member.id, member.guild.id)] = datetime.now()
            
        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            join_time = self.voice_join_times.pop((member.id, member.guild.id), None)
            if join_time:
                duration = int((datetime.now() - join_time).total_seconds())
                
                cursor = self.db.cursor()
                cursor.execute('''
                INSERT INTO activity_stats (user_id, guild_id, voice_time, last_updated)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, guild_id) 
                DO UPDATE SET
                    voice_time = voice_time + ?,
                    last_updated = CURRENT_TIMESTAMP
                ''', (member.id, member.guild.id, duration, duration))
                self.db.commit()

# Create and run the bot
bot = ActivityTracker()

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user}')
    print(f'Bot is in {len(bot.guilds)} servers')
    print('Use !stats or !stats @username to check activity statistics')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("Could not find that member. Please make sure you're mentioning a valid user.")
    elif isinstance(error, commands.errors.CommandInvokeError):
        await ctx.send("An error occurred while processing the command. Please try again.")
    else:
        await ctx.send(f"An error occurred: {str(error)}")

# Replace with your token
bot.run('MTMzODM3NzIwODY0ODk2MjEwOQ.GukXWs.XmiF7DgXIRP2XKQZasZUTXmUqfzdBmn81Lu3lw')
