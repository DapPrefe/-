import discord
from discord.ext import commands
import aiosqlite
from datetime import datetime

TOKEN = "MTM5MzQyMzU1MDEwNjMwODY2OQ.GK5iYU.Icy2HoQCrVkgWFqAP_rcVYyXdXRtWYEjhSKAgs"
LOG_CHANNEL_ID = 1393425901051707423  # ID лог-канала

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Бот запущен как {bot.user}')
    async with aiosqlite.connect("ratings.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                rater_id INTEGER,
                rated_id INTEGER,
                rating INTEGER,
                last_rated TEXT,
                UNIQUE(rater_id, rated_id)
            )
        """)
        await db.commit()

@bot.command()
async def rate(ctx, member: discord.Member = None, rating_raw: str = None):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    if not member or rating_raw is None:
        try:
            await ctx.author.send("❌ Неверный формат: `/rate @пользователь [оценка от 1 до 10]`")
        except discord.Forbidden:
            pass
        return

    try:
        rating = int(rating_raw)
    except ValueError:
        try:
            await ctx.author.send("❌ Оценка должна быть **числом от 1 до 10**.")
        except discord.Forbidden:
            pass
        return

    if member.id == ctx.author.id:
        try:
            await ctx.author.send("❌ Нельзя оценивать самого себя.")
        except discord.Forbidden:
            pass
        return
    if rating < 1 or rating > 10:
        try:
            await ctx.author.send("❌ Оценка должна быть от **1 до 10**.")
        except discord.Forbidden:
            pass
        return

    async with aiosqlite.connect("ratings.db") as db:
        await db.execute("""
            INSERT OR REPLACE INTO ratings (rater_id, rated_id, rating, last_rated)
            VALUES (?, ?, ?, ?)
        """, (ctx.author.id, member.id, rating, datetime.now().isoformat()))
        await db.commit()

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"📊 {ctx.author.mention} поставил {rating}/10 {member.mention}")

    try:
        await ctx.author.send(f"⭐ Вы поставили **{rating}** звёзд пользователю {member.display_name}!")
    except discord.Forbidden:
        pass

@bot.command()
async def rating(ctx, member: discord.Member = None):
    try:
        await ctx.message.delete()
    except:
        pass

    member = member or ctx.author

    if not ctx.guild.get_member(member.id):
        try:
            await ctx.author.send("❌ Этого пользователя нет на сервере.")
        except discord.Forbidden:
            pass
        try:
            await ctx.message.delete()
        except:
            pass
        return

    async with aiosqlite.connect("ratings.db") as db:
        async with db.execute("SELECT AVG(rating), COUNT(*) FROM ratings WHERE rated_id = ?", (member.id,)) as cursor:
            avg, count = await cursor.fetchone()
            if count == 0:
                msg = await ctx.send(f"ℹ️ У {member.display_name} пока нет оценок.")
            else:
                msg = await ctx.send(f"📈 Рейтинг {member.display_name}: **{avg:.2f}/10** ({count} оценок)")
            await msg.delete(delay=15)

@bot.command()
async def leaderboard(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    async with aiosqlite.connect("ratings.db") as db:
        query = """
        SELECT rated_id, AVG(rating) as avg_rating, COUNT(*) as count
        FROM ratings
        GROUP BY rated_id
        HAVING count >= 2
        ORDER BY avg_rating DESC
        LIMIT 10
        """
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        msg = await ctx.send("ℹ️ Пока нет данных для рейтинга.")
        return await msg.delete(delay=15)

    text = "**🏆 Топ пользователей по рейтингу:**\n"
    for i, (user_id, avg_rating, count) in enumerate(rows, 1):
        user = await bot.fetch_user(user_id)
        text += f"{i}. {user.name} — {avg_rating:.2f}/10 ({count} оценок)\n"

    msg = await ctx.send(text)
    await msg.delete(delay=15)

@bot.event
async def on_member_remove(member):
    async with aiosqlite.connect("ratings.db") as db:
        # Удаляем оценки, которые оставил ушедший пользователь (rater_id)
        await db.execute("DELETE FROM ratings WHERE rater_id = ?", (member.id,))
        await db.commit()

bot.run(TOKEN)
