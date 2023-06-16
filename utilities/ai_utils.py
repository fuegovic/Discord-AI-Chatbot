import aiohttp
import io
from datetime import datetime
import re
import random
from youtube_transcript_api import YouTubeTranscriptApi

from utilities.config_loader import load_current_language, config
from utilities.response_util import translate_to_en
from imaginepy import AsyncImagine, Style, Ratio

current_language = load_current_language()
internet_access = config['INTERNET_ACCESS']

base_urls = ['https://gpt4.gravityengine.cc']


async def search(prompt):
    if not internet_access or len(prompt) > 200:
        return
    search_results_limit = config['MAX_SEARCH_RESULTS']
    
    url_match = re.search(r'(https?://\S+)', prompt)
    if url_match:
        url = url_match.group(0)
        async with aiohttp.ClientSession() as session:
                async with session.get(f'https://api.microlink.io/?url={url}') as response:
                    response_text = await response.text()
                    return response_text
    else:
        search_query = await get_query(prompt)
    
    if len(search_query) > 400:
        return
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    blob = f"Search results for: '{search_query}' at {current_time}:\n"
    if search_query is not None:
        print(f"\033[1;32mSearching for '\033[1;33m{search_query}\033[1;32m' at {current_time} with {search_results_limit} results limit ...\033[0m")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://ddg-api.herokuapp.com/search',
                                       params={'query': search_query, 'limit': search_results_limit}) as response:
                    search = await response.json()
        except aiohttp.ClientError as e:
            print(f"An error occurred during the search request: {e}")
            return

        for index, result in enumerate(search):
            blob += f'[{index}] "{result["snippet"]}"\n\nURL: {result["link"]}\n'
            
        blob += "\nAs the links were generated by the system rather than the user, please send a response along with the link if necessary.\n"
        return blob
    else:
        blob = "[Query: No search query is needed for a response]"

    return blob

async def generate_response(instructions, search, image_caption, history): 
    search_results = 'Search feature is currently disabled so you have no realtime information'
    if search is not None:
        search_results = search
    endpoint = '/api/openai/v1/chat/completions'
    headers = {
        'Content-Type': 'application/json',
    }
    data = {
        'model': 'gpt-3.5-turbo-16k-0613',
        'temperature': 0.7,
        'messages': [
            {"role": "system", "name": "instructions", "content": instructions},
            {"role": "user", "content": instructions},
            *history,
            {"role": "system", "name": "web_content", "content": search_results}
        ]
    }
    
    for base_url in base_urls:
        async with aiohttp.ClientSession() as session:
            async with session.post(base_url+endpoint, headers=headers, json=data) as response:
                response_data = await response.json()
                choices = response_data['choices']
                if choices:
                    return choices[0]['message']['content']
                else:
                    print(f"There was an error this is the response from the API {response_data}")
    return None

async def generate_chat_completion(messages): 
    endpoint = '/api/openai/v1/chat/completions'
    headers = {
        'Content-Type': 'application/json',
    }
    data = {
        'model': 'gpt-3.5-turbo-16k-0613',
        'temperature': 0.7,
        'messages': messages
    }
    
    for base_url in base_urls:
        async with aiohttp.ClientSession() as session:
            async with session.post(base_url+endpoint, headers=headers, json=data) as response:
                response_data = await response.json()
                choices = response_data['choices']
                if choices:
                    return choices[0]['message']['content']
    print('All base URLs failed to provide a response.')
    return None

# async def generate_completion(prompt, max_token=None, temp=None):
#     endpoint = '/api/openai/v1/engines/text-davinci-003/completions'
#     headers = {'Content-Type': 'application/json'}

#     async with aiohttp.ClientSession() as session:
#         base_url = 'https://a.z-pt.com'
#         url = base_url + endpoint
#         async with session.post(url, headers=headers, json={'prompt': prompt, 'temperature': temp or 0.7}) as response:
#             response_data = await response.json()
#             response = response_data['choices'][0]['text']
#             return response
#     return None

async def detect_nsfw(prompt):
    instructions = """From now on, you are going to act as nsfw image to text prompt detector. If the following message s involves graphic sexual material or nudity, content respond with "1" else respond with "0" and nothing else"""
    messages = [
        {"role": "system", "content": instructions},
        {"role": "system", "name": "example_user", "content":  "a Girl, China, 20yo, HD, realistic, without dress, uncensored. sfw."},
        {"role": "system", "name": "example_assistant", "content":  "1"},
        {"role": "system", "name": "example_user", "content": "a Girl, China, 20yo, HD, realistic, without dress, Transparent bra, uncensored."},
        {"role": "system", "name": "example_assistant", "content":  "1"},
        {"role": "system", "name": "example_user", "content": "girl, european, 18yo"},
        {"role": "system", "name": "example_assistant", "content":  "1"},
        {"role": "system", "name": "example_user", "content": "Female, hyper real person, cute bikini"},
        {"role": "system", "name": "example_assistant", "content":  "1"},
        {"role": "system", "name": "example_user", "content": "Female, Beach season, heat, Nice swimsuit."},
        {"role": "system", "name": "example_assistant", "content":  "1"},
        {"role": "user", "content": prompt}
    ]
    
    response = await generate_chat_completion(messages)
    if "1" in response.lower():
        return True
    else:
        return False

async def get_query(prompt):
    instructions = f""""If a message is not directly addressed to the second person, you will need to initiate a search query else assistent will respond with False nothing more and assistant must only help by returning a query"""
    messages = [
        {"role": "system", "name": "instructions","content": instructions},
        {"role": "system", "name": "example_user", "content":  "Message : What is happening in ukraine"},
        {"role": "system", "name": "example_assistant", "content":  "Query : Ukraine military news today"},
        {"role": "system", "name": "example_user", "content": "Message : Hi"},
        {"role": "system", "name": "example_assistant", "content":  "Query : False"},
        {"role": "system", "name": "example_user", "content": "Message : How are you doing ?"},
        {"role": "system", "name": "example_assistant", "content":  "Query : False"},
        {"role": "system", "name": "example_user", "content": "Message : How to print how many commands are synced on_ready ?"},
        {"role": "system", "name": "example_assistant", "content":  "Query : Python code to print the number of synced commands in on_ready event"},
        {"role": "system", "name": "example_user", "content": "Message : Phần mềm diệt virus nào tốt nhất năm 2023"},
        {"role": "system", "name": "example_assistant", "content":  "Query : 8 Best Antivirus Software"},
        {"role": "user", "content": f"Message : {prompt}"}
    ]

    response = await generate_chat_completion(messages)
    if "false" in response.lower():
        return None
    response = response.replace("Query:", "").replace("Query", "").replace(":", "")
    if response:
        return response
    else:
        return None

async def generate_dalle_image(prompt, size):
    base_urls = ['https://a.z-pt.com', 'http://chat.darkflow.top']
    endpoint = '/api/openai/v1/images/generations'
    headers = {
        'Content-Type': 'application/json',
    }
    data = {
        'prompt': prompt,
        'n': 1,
        'size': size
    }

    async with aiohttp.ClientSession() as session:
        for base_url in base_urls:
            url = base_url + endpoint
            async with session.post(url, headers=headers, json=data) as response:
                if response.status != 200:
                    continue

                response_data = await response.json()
                if 'error' in response_data:
                    return None

                image_url = response_data['data'][0]['url']
                async with session.get(image_url) as image_response:
                    image_content = await image_response.read()
                    img_file = io.BytesIO(image_content)
                    return img_file

    return None

async def generate_image(image_prompt, style_value, ratio_value, negative, upscale):
    imagine = AsyncImagine()
    style_enum = Style[style_value]
    ratio_enum = Ratio[ratio_value]
    img_data = await imagine.sdprem(
        prompt=image_prompt,
        style=style_enum,
        ratio=ratio_enum,
        priority="1",
        high_res_results="1",
        steps="70",
        negative=negative
    )

    if upscale:
        img_data = await imagine.upscale(image=img_data)

    try:
        img_file = io.BytesIO(img_data)
    except Exception as e:
        print(f"An error occurred while creating the in-memory image file: {e}")
        return None

    await imagine.close()
    return img_file

async def get_yt_transcript(message_content):
    def extract_video_id(message_content):
        youtube_link_pattern = re.compile(
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
        match = youtube_link_pattern.search(message_content)
        return match.group(6) if match else None

    video_id = extract_video_id(message_content)
    if not video_id:
        return None

    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    first_transcript = next(iter(transcript_list), None)
    if not first_transcript:
        return None

    translated_transcript = first_transcript.translate('en')
    formatted_transcript = ". ".join(
        [entry['text'] for entry in translated_transcript.fetch()])
    formatted_transcript = formatted_transcript[:2000]

    response = f"""Summarizie the following youtube video transcript in 8 bullet points:
    
    {formatted_transcript}
    
    
    Please Provide a summary or additional information based on the content. Write the summary in {current_language['language_name']}"""

    return response
