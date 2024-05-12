from openai import OpenAI
from dotenv import load_dotenv
import os
import tiktoken

load_dotenv()
TOKEN = os.environ.get('OPENAI_TOKEN')
MODEL = "gpt-4-turbo"
client = OpenAI(api_key=TOKEN)

def process_transcript(messages):
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system", 
                "content": "You are a discord bot that summarizes conversations that occur in a student advocacy discord server. " + 
                    "Format the report in discord's formatting scheme- do not encapsulate it in triple ticks as the text will directly be sent as a message. Topics not related to academic issues should be mentioned but do not need much detail- conversely topics related to NJIT/Academics should be summarized in detail."
            },
            {
                "role": "user", 
                "content": messages
            }
        ]
    )

    return completion.choices[0].message.content

def combine_reports(messages):
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system", 
                "content": "You are a discord bot that summarizes conversations that occur in a student advocacy discord server. These are a series of reports generated on chunks of conversation, in chonological order. Combine them into one comprehensive report." + 
                    "Format the report in discord's formatting scheme- do not encapsulate it in triple ticks as the text will directly be sent as a message. Topics not related to academic issues should be mentioned but do not need much detail- conversely topics related to NJIT/Academics should be summarized in detail."
            },
            {
                "role": "user", 
                "content": messages
            }
        ]
    )

    return completion.choices[0].message.content

def split_text(text, max_size):
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(text)
    for i in range(0, len(tokens), max_size):
        # Join tokens from i to i+max_size, and convert list of tokens back to string
        yield tokenizer.decode(tokens[i:i+max_size])

def process_large_text(text, max_tokens=100000):
    tokenizer = tiktoken.get_encoding("cl100k_base")
    token_count = len(tokenizer.encode(text))
    
    if token_count <= max_tokens:
        return process_transcript(text)
    
    # Split the text into manageable parts
    parts = list(split_text(text, max_tokens))
    reports = [process_transcript(part) for part in parts]
    
    # Combine the reports using the same LLM for a final cohesive report
    if len(reports) > 1:
        combined_reports = " ".join(reports)
        final_report = process_transcript(combined_reports)
        return final_report
    else:
        return reports[0]