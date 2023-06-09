#!/usr/bin/env python3
"""
https://github.com/1RO8s/discord-summarizer
  by [1RO8s](https://twitter.com/kizzo168))
  2023- [APACHE LICENSE, 2.0](https://www.apache.org/licenses/LICENSE-2.0)
"""
import os
import re
import sys
from datetime import datetime, timedelta
import pytz
import openai
import discord
from discord.errors import DiscordException
from utils import remove_emoji, retry

# for local test
from dotenv import load_dotenv
load_dotenv()

# Load settings from environment variables
OPEN_AI_TOKEN = str(os.environ.get('OPEN_AI_TOKEN')).strip()
LANGUAGE = str(os.environ.get('LANGUAGE') or "Japanese").strip()
TEMPERATURE = float(os.environ.get('TEMPERATURE') or 0.3)
CHAT_MODEL = str(os.environ.get('CHAT_MODEL') or "gpt-3.5-turbo").strip()
MAX_BODY_TOKENS = 3000
DISCORD_TOKEN = str(os.environ.get('DISCORD_TOKEN')).strip()
SERVER_ID = str(os.environ.get('SERVER_ID')).strip()
SUMMARY_CHANNEL_ID = str(os.environ.get('SUMMARY_CHANNEL_ID')).strip()
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)
TIMEZONE_STR = str(os.environ.get('TIMEZONE') or 'Asia/Tokyo').strip()
DEBUG = str(os.environ.get('DEBUG') or "").strip() != ""

print(f"""
LANGUAGE = {LANGUAGE}
TEMPERATURE = {TEMPERATURE}
CHAT_MODEL = {CHAT_MODEL}
MAX_BODY_TOKENS = {MAX_BODY_TOKENS}
SERVER_ID = {SERVER_ID}
SUMMARY_CHANNEL_ID = {SUMMARY_CHANNEL_ID}
TIMEZONE_STR = {TIMEZONE_STR}
DEBUG = {DEBUG}
""")

def summarize(text: str, language: str = "Japanese"):
    """
    Summarize a chat log in bullet points, in the specified language.

    Args:
        text (str): The chat log to summarize, in the format "Speaker: Message" separated by line breaks.
        language (str, optional): The language to use for the summary. Defaults to "Japanese".

    Returns:
        str: The summarized chat log in bullet point format.

    Examples:
        >>> summarize("Alice: Hi\nBob: Hello\nAlice: How are you?\nBob: I'm doing well, thanks.")
        '- Alice greeted Bob.\n- Bob responded with a greeting.\n- Alice asked how Bob was doing.\n- Bob replied that he was doing well.'
    """
    response = openai.ChatCompletion.create(
        model=CHAT_MODEL,
        temperature=TEMPERATURE,
        messages=[{
            "role":
            "system",
            "content":
            "\n".join([
                'The chat log format consists of one line per message in the format "Speaker: Message".',
                "The `\\n` within the message represents a line break."
                f'The user understands {language} only.',
                f'So, The assistant need to speak in {language}.',
            ])
        }, {
            "role":
            "user",
            "content":
            "\n".join([
                f"Please meaning summarize the following chat log to flat bullet list in {language} by polite language.",
                "It isn't line by line summary.",
                "Do not include greeting/salutation/polite expressions in summary.",
                "With make it easier to read."
                f"Write in {language}.", "", text
            ])
        }])

    if DEBUG:
        print(response["choices"][0]["message"]['content'])
    return response["choices"][0]["message"]['content']

def get_time_range():
    """
    Get a time range starting from 25 hours ago and ending at the current time.

    Returns:
        tuple: A tuple containing the start and end times of the time range, as datetime objects.

    Examples:
        >>> start_time, end_time = get_time_range()
        >>> print(start_time, end_time)
        2022-05-17 09:00:00+09:00 2022-05-18 10:00:00+09:00
    """
    hours_back = 25
    timezone = pytz.timezone(TIMEZONE_STR)
    now = datetime.now(timezone)
    yesterday = now - timedelta(hours=hours_back)
    start_time = datetime(yesterday.year, yesterday.month, yesterday.day,
                          yesterday.hour, yesterday.minute, yesterday.second)
    end_time = datetime(now.year, now.month, now.day, now.hour, now.minute,
                        now.second)
    return start_time, end_time

def estimate_openai_chat_token_count(text: str) -> int:
    """
    Estimate the number of OpenAI API tokens that would be consumed by sending the given text to the chat API.

    Args:
        text (str): The text to be sent to the OpenAI chat API.

    Returns:
        int: The estimated number of tokens that would be consumed by sending the given text to the OpenAI chat API.

    Examples:
        >>> estimate_openai_chat_token_count("Hello, how are you?")
        7
    """
    # Split the text into words and count the number of characters of each type
    pattern = re.compile(
        r"""(
            \d+       | # digits
            [a-z]+    | # alphabets
            \s+       | # whitespace
            .           # other characters
            )""", re.VERBOSE | re.IGNORECASE)
    matches = re.findall(pattern, text)

    # based on https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
    def counter(tok):
        if tok == ' ' or tok == '\n':
            return 0
        elif tok.isdigit() or tok.isalpha():
            return (len(tok) + 3) // 4
        else:
            return 1

    return sum(map(counter, matches))

def split_messages_by_token_count(messages: list[str]) -> list[list[str]]:
    """
    Split a list of strings into sublists with a maximum token count.

    Args:
        messages (list[str]): A list of strings to be split.

    Returns:
        list[list[str]]: A list of sublists, where each sublist has a token count less than or equal to max_body_tokens.
    """
    body_token_counts = [
        estimate_openai_chat_token_count(message) for message in messages
    ]
    result = []
    current_sublist = []
    current_count = 0

    for message, count in zip(messages, body_token_counts):
        if current_count + count <= MAX_BODY_TOKENS:
            current_sublist.append(message)
            current_count += count
        else:
            result.append(current_sublist)
            current_sublist = [message]
            current_count = count

    result.append(current_sublist)
    return result

@client.event
async def on_ready():
    # time range
    start_time, end_time = get_time_range()
    print(f"{start_time.strftime('%Y/%m/%d %H:%m')} - {end_time.strftime('%Y/%m/%d %H:%m')}")

    guild = next((g for g in client.guilds if g.id == int(SERVER_ID)),None)    
    if guild == None:
        await client.close()

    result_text = []
    for channel in guild.text_channels:
        if channel.id == int(SUMMARY_CHANNEL_ID): continue
        history = channel.history(after=start_time, before=end_time)
        messages = []
        async for msg in history:
            if msg.clean_content == "": continue
            messages.append(f"{msg.author.display_name}:{msg.clean_content}")
        if not messages :
            result_text.append(f"<#{channel.id}>\n  -- No messages --")
            continue 
        messages = list(map(remove_emoji, messages))
        result_text.append(f"<#{channel.id}>")
        for spilitted_messages in split_messages_by_token_count(messages):
            text = summarize("\n".join(spilitted_messages), LANGUAGE)
            result_text.append(text)

    title = (f"__{start_time.strftime('%Y-%m-%d')} public channels summary__\n\n")
    summary_channnel = next((c for c in guild.text_channels if c.id == int(SUMMARY_CHANNEL_ID)),None)

    if DEBUG:
        print(title + "\n".join(result_text))
    else:
        async def retry_send():
            try:
                await summary_channnel.send(title + "\n".join(result_text))
            except DiscordException:
                retry(retry_send, DiscordException)
        await retry_send()
    await client.close()

if __name__ == '__main__':
    if OPEN_AI_TOKEN == "" or DISCORD_TOKEN == "" or SERVER_ID == "" or SUMMARY_CHANNEL_ID == "":
        print("OPEN_AI_TOKEN, DISCORD_TOKEN, SERVER_ID, SUMMARY_CHANNEL_ID must be set.")
        sys.exit(1)
    openai.api_key = OPEN_AI_TOKEN
    client.run(DISCORD_TOKEN) 