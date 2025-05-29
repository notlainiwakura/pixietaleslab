from __future__ import annotations

import os
import random
import tempfile
from typing import Callable, ClassVar, List, Tuple
import time
import re
import logging

from pathlib import Path
from dotenv import load_dotenv
import json
from pydantic import Field

# Load environment variables from project root .env
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
import google.auth
import google.auth.transport.requests
import requests
from google.adk.agents import Agent, SequentialAgent, ParallelAgent

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# ────────────────────────────────  Leaf Agents  ────────────────────────────────

class UserInputAgent(Agent):
    """Validates and/or randomises end‑user parameters."""

    DEFAULTS: ClassVar[dict] = {
        "character_name": ["Barnaby", "Luna", "Max"],
        "animal": ["rabbit", "fox", "dog", "cat", "bear"],
        "setting": ["Enchanted forest", "Magical kingdom", "Sunny meadow"],
        "gender": ["male", "female"],
        "age": ["3‑5"],
        "voice": ["female", "male"],
    }

    def run(self, params: dict, *, memory: dict | None = None):
        logging.info(f"[UserInputAgent] Input params: {params}")
        processed: dict = {}
        randomise = params.get("randomize_all")
        for key in ["character_name", "animal", "gender", "age"]:
            processed[key] = (
                random.choice(self.DEFAULTS[key])
                if randomise
                else params.get(key, random.choice(self.DEFAULTS[key]))
            )
        processed["voice"] = "female"
        processed["length"] = "short"
        custom_elements = params.get("custom_elements")
        user_setting = params.get("setting")
        if user_setting:
            # User selected a setting from the dropdown; it takes priority
            processed["setting"] = user_setting
            if custom_elements:
                import re
                # Remove setting-related phrases from custom_elements
                custom_elements_cleaned = re.sub(r"\b(in|at|on) the [A-Za-z ]+", "", custom_elements, flags=re.IGNORECASE)
                processed["custom_elements"] = custom_elements_cleaned.strip() or None
            else:
                processed["custom_elements"] = None
        elif custom_elements:
            processed["custom_elements"] = custom_elements if custom_elements else None
            # Try to detect a setting in the custom elements (simple heuristic: look for 'in the' or 'at the' or 'on the')
            import re
            setting_match = re.search(r"\b(in|at|on) the ([A-Za-z ]+)", custom_elements, re.IGNORECASE)
            if setting_match:
                processed["setting"] = setting_match.group(0)[3:].strip()  # e.g., 'the jungle'
            else:
                # No setting in custom elements, randomize
                processed["setting"] = random.choice(self.DEFAULTS["setting"])
        else:
            processed["setting"] = (
                random.choice(self.DEFAULTS["setting"])
                if randomise
                else params.get("setting", random.choice(self.DEFAULTS["setting"]))
            )
        # Set pronouns based on gender
        gender = processed["gender"].lower()
        if gender == "male":
            processed["pronoun_subject"] = "he"
            processed["pronoun_object"] = "him"
            processed["pronoun_possessive"] = "his"
        else:
            processed["pronoun_subject"] = "she"
            processed["pronoun_object"] = "her"
            processed["pronoun_possessive"] = "her"
        if memory is not None:
            memory["user_params"] = processed
        logging.info(f"[UserInputAgent] Output: {processed}")
        return processed

class StoryGeneratorAgent(Agent):
    """Generates the story via Vertex AI Gemini (fallback to OpenAI/Mock)."""

    def run(
        self,
        params: dict,
        *,
        memory: dict | None = None,
        send: Callable | None = None,
        receive: Callable | None = None,
    ):
        logging.info(f"[StoryGeneratorAgent] Input: {params}")
        custom_elements = params.get("custom_elements")
        if custom_elements:
            # If custom elements are present, use them in the prompt and avoid duplicating the setting if it's already in custom_elements
            prompt = (
                "Write a children's story for ages {age} with the following details:\n"
                "Main character: {character_name}, who is a {gender} {animal}\n"
                "{custom_elements}\n"
                "Length: {length}\n"
                "The story should be gentle, imaginative, and safe. The story should teach a moral lesson.\n"
                "Use the pronouns {pronoun_subject}, {pronoun_object}, and {pronoun_possessive} for the main character throughout the story."
            ).format(
                character_name=params["character_name"],
                animal=params["animal"],
                gender=params["gender"],
                custom_elements=custom_elements,
                length=params["length"],
                age=params["age"],
                pronoun_subject=params["pronoun_subject"],
                pronoun_object=params["pronoun_object"],
                pronoun_possessive=params["pronoun_possessive"]
            )
        else:
            prompt = (
                "Write a children's story for ages {age} with the following details:\n"
                "Main character: {character_name}, who is a {gender} {animal}\n"
                "Setting: {setting}\n"
                "Length: {length}\n"
                "The story should be gentle, imaginative, and safe. The story should teach a moral lesson.\n"
                "Use the pronouns {pronoun_subject}, {pronoun_object}, and {pronoun_possessive} for the main character throughout the story."
            ).format(
                character_name=params["character_name"],
                animal=params["animal"],
                setting=params["setting"],
                length=params["length"],
                age=params["age"],
                gender=params["gender"],
                pronoun_subject=params["pronoun_subject"],
                pronoun_object=params["pronoun_object"],
                pronoun_possessive=params["pronoun_possessive"]
            )

        story: str | None = None
        try:
            project = os.environ["GOOGLE_CLOUD_PROJECT"]
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us‑central1")
            model = (
                f"projects/{project}/locations/{location}/publishers/google/"
                f"models/gemini-2.0-flash-001"
            )
            url = f"https://{location}-aiplatform.googleapis.com/v1/{model}:streamGenerateContent"
            creds, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            creds.refresh(google.auth.transport.requests.Request())
            headers = {
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json; charset=utf-8",
            }
            data = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}],
                    }
                ]
            }
            r = requests.post(url, json=data, headers=headers, stream=True, timeout=60)
            r.raise_for_status()
            response_text = ""
            for line in r.iter_lines():
                if not line:
                    continue
                response_text += line.decode()
            try:
                response_json = json.loads(response_text)
            except Exception as e:
                print("Failed to parse Gemini response as JSON array:", e)
                response_json = []
            story = ""
            for obj in response_json:
                if "candidates" not in obj:
                    continue
                for cand in obj["candidates"]:
                    for part in cand.get("content", {}).get("parts", []):
                        if "text" in part:
                            story += part["text"]
            if not story:
                raise RuntimeError("Gemini returned empty result")
        except Exception as e: 
            print("Gemini API call failed:", e)
            # Minimal mock fallback
            story = (
                f"Once upon a time in the {params['setting']}, there was "
                f"{params['animal'].lower()}. The tale teaches us: "
                f"{params.get('custom_elements', 'a moral lesson')}. (mock story)"
            )

        if memory is not None:
            memory["story"] = story
        if send is not None:
            send("CoherenceAgent", story)
        logging.info(f"[StoryGeneratorAgent] Output: {story[:200]}{'...' if len(story) > 200 else ''}")
        return story

class StorySummaryAgent(Agent):
    """Summarizes the story for illustration context."""
    def run(self, story: str, *, memory: dict | None = None):
        try:
            # Use Gemini to summarize the story
            project = os.environ["GOOGLE_CLOUD_PROJECT"]
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            model = (
                f"projects/{project}/locations/{location}/publishers/google/"
                f"models/gemini-2.0-flash-001"
            )
            url = f"https://{location}-aiplatform.googleapis.com/v1/{model}:streamGenerateContent"
            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            creds.refresh(google.auth.transport.requests.Request())
            headers = {
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json; charset=utf-8",
            }
            prompt = f"Summarize the following children's story in 2-3 sentences, focusing on the main character, setting, and main events.\n\nStory:\n{story}"
            data = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}],
                    }
                ]
            }
            r = requests.post(url, json=data, headers=headers, stream=True, timeout=60)
            r.raise_for_status()
            response_text = ""
            for line in r.iter_lines():
                if not line:
                    continue
                response_text += line.decode()
            try:
                response_json = json.loads(response_text)
            except Exception as e:
                print("Failed to parse Gemini response as JSON array (summary):", e)
                response_json = []
            summary = ""
            for obj in response_json:
                if "candidates" not in obj:
                    continue
                for cand in obj["candidates"]:
                    for part in cand.get("content", {}).get("parts", []):
                        if "text" in part:
                            summary += part["text"]
            if not summary:
                raise RuntimeError("Gemini returned empty summary")
        except Exception as e:
            print("Gemini summary API call failed:", e)
            summary = story[:200]  # fallback: first 200 chars
        if memory is not None:
            memory["summary"] = summary
        return summary

class StoryElementsAgent(Agent):
    """Extracts main character(s) and setting from the story using Gemini."""
    def run(self, story: str, *, memory: dict | None = None):
        logging.info(f"[StoryElementsAgent] Input story: {story[:200]}{'...' if len(story) > 200 else ''}")
        try:
            project = os.environ["GOOGLE_CLOUD_PROJECT"]
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            model = (
                f"projects/{project}/locations/{location}/publishers/google/"
                f"models/gemini-2.0-flash-001"
            )
            url = f"https://{location}-aiplatform.googleapis.com/v1/{model}:streamGenerateContent"
            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            creds.refresh(google.auth.transport.requests.Request())
            headers = {
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json; charset=utf-8",
            }
            prompt = (
                "Extract the main character's name and the main setting from the following children's story. "
                "Respond ONLY in JSON, like: {\"character\": \"Barnaby\", \"setting\": \"Glimmering Glades\"}. "
                "Do not include any explanation or extra text.\n\nStory:\n" + story
            )
            data = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}],
                    }
                ]
            }
            r = requests.post(url, json=data, headers=headers, stream=True, timeout=60)
            r.raise_for_status()
            response_text = ""
            for line in r.iter_lines():
                if not line:
                    continue
                response_text += line.decode()
            print("Gemini raw response (elements):", response_text)
            try:
                response_json = json.loads(response_text)
            except Exception as e:
                print("Failed to parse Gemini response as JSON array (elements):", e)
                response_json = []
            character = None
            setting = None
            for obj in response_json:
                if "candidates" not in obj:
                    continue
                for cand in obj["candidates"]:
                    for part in cand.get("content", {}).get("parts", []):
                        if "text" in part:
                            json_text = part["text"]
                            print("Gemini candidate text (elements):", json_text)
                            import re
                            match = re.search(r'\{.*?\}', json_text, re.DOTALL)
                            if match:
                                try:
                                    parsed = json.loads(match.group(0))
                                    character = parsed.get("character")
                                    setting = parsed.get("setting")
                                    print("Parsed character:", character, "Parsed setting:", setting)
                                except Exception as e2:
                                    print("Failed to parse character/setting JSON (regex):", e2)
                                    print("Raw JSON text:", match.group(0))
            if not character:
                character = "the main character"
            if not setting:
                setting = "the main setting"
        except Exception as e:
            print("Gemini elements API call failed:", e)
            character = "the main character"
            setting = "the main setting"
        if memory is not None:
            memory["character"] = character
            memory["setting"] = setting
        logging.info(f"[StoryElementsAgent] Output: character={character}, setting={setting}")
        return {"character": character, "setting": setting}

class PromptExampleAgent(Agent):
    """Generates image descriptions for each scene using few-shot examples."""
    FEW_SHOT_EXAMPLES: ClassVar[List[Tuple[str, str]]] = [
        ("The puppy helps his little sister find her lost toy in the garden.", "A puppy and a smaller puppy searching together in a garden, both looking happy."),
        ("The cat chases a butterfly.", "A cat leaping playfully after a butterfly in a sunny field."),
        ("Barnaby was a very brave rabbit.", "A rabbit standing tall and proud."),
        ("He lived in a cozy burrow nestled deep in the Enchanted Forest.", "A rabbit next to a cozy burrow in a magical forest."),
        ("One sunny morning, Barnaby hopped out of his burrow, ready for an adventure.", "A rabbit hopping out of a burrow with the sun shining.") ,
        ("Barnaby peeked behind a giant, sparkly mushroom. There, huddled under its cap, was a little bluebird with a droopy wing.", "A rabbit and a small bluebird under a giant mushroom."),
        ("The little bluebird, feeling a tiny bit better, carefully climbed onto Barnaby's fluffy back. Barnaby slowly, slowly, hopped towards the tall oak tree, being extra careful not to jostle the bluebird's wing.", "A rabbit carrying a bluebird on its back, heading toward a tall oak tree."),
        ("The big bluebird chirped happily and offered Barnaby a juicy berry. 'Thank you for being so kind,' it chirped. 'You helped my baby get home safe!'", "A happy bluebird giving a berry to a rabbit."),
        ("He hopped back towards his burrow, the sun warming his fur, knowing that even the bravest rabbit could make the world a little brighter by being kind.", "A rabbit hopping home in the sunshine, looking happy."),
        ("The lion shares his lunch with a hungry mouse.", "A lion and a mouse sitting together, sharing food, both smiling."),
        ("The elephant splashes water on her friends to cool them down.", "An elephant playfully spraying water on other animals, everyone laughing."),
    ]

    def run(self, story: str, scene: str, *, memory: dict | None = None):
        logging.info(f"[PromptExampleAgent] Input scene: {scene}")
        try:
            project = os.environ["GOOGLE_CLOUD_PROJECT"]
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            model = (
                f"projects/{project}/locations/{location}/publishers/google/"
                f"models/gemini-2.0-flash-001"
            )
            url = f"https://{location}-aiplatform.googleapis.com/v1/{model}:streamGenerateContent"
            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            creds.refresh(google.auth.transport.requests.Request())
            headers = {
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json; charset=utf-8",
            }
            prompt = (
                "You are an expert at writing image descriptions for a children's coloring book.\n"
                "For each scene, describe a simple, childlike doodle that shows the main character(s) doing the main action in the setting. "
                "Include the key action, setting, and emotion, but keep the drawing simple and easy to color.\n"
                "Do NOT draw any people, humans, or stick-figures of people.\n"
                "The drawing should look like a child's doodle, with only outlines, no color, no shading, no background, and no text.\n\n"
            )
            # Add few-shot examples (context-rich)
            for ex_scene, ex_img in self.FEW_SHOT_EXAMPLES:
                prompt += f"Scene: {ex_scene}\nImage: {ex_img}\n\n"
            # Style instructions (repeated and at the end for emphasis)
            prompt += (
                "\nIMPORTANT STYLE INSTRUCTIONS (repeat):\n"
                "- ONLY outlines, black and white, no color.\n"
                "- NO shading, NO background, NO details, NO text, NO numbers.\n"
                "- The simplest possible lines, like a child's doodle of an animal.\n"
                "- The drawing should look like a child's doodle, not a professional illustration.\n"
                "- If you add any people, stick-figures of people, or realism, you will lose points. Simpler is better.\n\n"
                "Now, for the following scene, write the image description in this simple, childlike animal doodle style.\n\n"
                f"Scene: {scene}\nImage:"
            )
            data = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}],
                    }
                ]
            }
            r = requests.post(url, json=data, headers=headers, stream=True, timeout=60)
            r.raise_for_status()
            response_text = ""
            for line in r.iter_lines():
                if not line:
                    continue
                response_text += line.decode()
            try:
                response_json = json.loads(response_text)
            except Exception as e:
                print("Failed to parse Gemini response as JSON array (prompt example):", e)
                response_json = []
            img_desc = ""
            for obj in response_json:
                if "candidates" not in obj:
                    continue
                for cand in obj["candidates"]:
                    for part in cand.get("content", {}).get("parts", []):
                        if "text" in part:
                            img_desc += part["text"]
            if not img_desc:
                img_desc = "A simple doodle showing the main character(s) doing the main action in the setting."
        except Exception as e:
            print("Gemini prompt example API call failed:", e)
            img_desc = "A simple doodle showing the main character(s) doing the main action in the setting."
        if memory is not None:
            memory.setdefault("img_descs", []).append(img_desc)
        logging.info(f"[PromptExampleAgent] Output: {img_desc}")
        return img_desc.strip()

class CoherenceAgent(Agent):
    """Splits story into scenes (by paragraph) & crafts illustration prompts."""

    def run(
        self,
        story: str,
        params: dict,
        *,
        memory: dict | None = None,
        send: Callable | None = None,
    ):
        logging.info(f"[CoherenceAgent] Input story: {story[:200]}{'...' if len(story) > 200 else ''}")
        # Split story into scenes by paragraph (double newlines)
        raw_scenes = [p.strip() for p in story.split('\n\n') if p.strip()]
        character = memory["character"] if memory and "character" in memory else "the main character"
        setting = memory["setting"] if memory and "setting" in memory else "the main setting"
        animal = params["animal"] if "animal" in params else "animal"
        style_info = (
            "• This is for a children's coloring book. Only draw the outlines. Make all objects large and easy to color.\n"
            "• Draw ONLY in black and white. NO color.\n"
            "• Use the simplest possible lines, like a stick-figure or a drawing by a 5-year-old.\n"
            "• NO shading, NO background, NO details, NO color, NO text, NO numbers.\n"
            "• The drawing should look like a child's doodle, not a professional illustration.\n"
        )
        prompts = []
        prompt_agent = PromptExampleAgent(name="PromptExampleAgent")
        for scene in raw_scenes:
            context = (
                f"{style_info}Animal: {animal}\nSetting: {setting}\n\nScene: {scene}\nImage:"
            )
            img_desc = prompt_agent.run(story, context)
            prompt = style_info + img_desc
            logging.info(f"[CoherenceAgent] Scene: {scene}")
            logging.info(f"[CoherenceAgent] Prompt sent to PromptExampleAgent: {context}")
            logging.info(f"[CoherenceAgent] Image description: {img_desc}")
            prompts.append(prompt)
        logging.info(f"[CoherenceAgent] Prompts: {prompts}")
        if memory is not None:
            memory["prompts"] = prompts
            memory["scenes"] = raw_scenes
        if send is not None:
            send("IllustrationGeneratorAgent", prompts)
        return prompts

class IllustrationGeneratorAgent(Agent):
    """Generates illustrations using Vertex AI Imagen 4."""

    def run(
        self,
        prompts: list[str],
        style: str,
        *,
        memory: dict | None = None,
        artifact: dict | None = None,
    ):
        logging.info(f"[IllustrationGeneratorAgent] Received {len(prompts)} prompts.")
        import base64
        images = []
        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        model = (
            f"projects/{project}/locations/{location}/publishers/google/"
            f"models/imagegeneration"
        )
        url = f"https://{location}-aiplatform.googleapis.com/v1/{model}:predict"
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(google.auth.transport.requests.Request())
        headers = {
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        max_images = len(prompts) 
        for i, prompt in enumerate(prompts[:max_images]):
            logging.info(f"[IllustrationGeneratorAgent] Prompt {i}: {prompt}")
            data = {
                "instances": [
                    {"prompt": prompt}
                ]
            }
            for attempt in range(2):  # Try up to 2 times
                try:
                    r = requests.post(url, json=data, headers=headers, timeout=120)
                    r.raise_for_status()
                    resp = r.json()
                    if "predictions" in resp and resp["predictions"]:
                        img_b64 = resp["predictions"][0]["bytesBase64Encoded"]
                        img_bytes = base64.b64decode(img_b64)
                        img_path = os.path.join(tempfile.gettempdir(), f"illustration_{i}.png")
                        with open(img_path, "wb") as f:
                            f.write(img_bytes)
                        images.append(img_path)
                        logging.info(f"[IllustrationGeneratorAgent] Saved image {i}: {img_path}")
                        break
                    else:
                        logging.warning(f"Empty or unexpected response for prompt {i}: {resp}")
                        if attempt == 0:
                            time.sleep(10)
                        else:
                            images.append(f"mock_image_{i}.png")
                except requests.exceptions.HTTPError as e:
                    if r.status_code == 429:
                        print(f"429 Too Many Requests for prompt {i}, retrying after delay...")
                        time.sleep(10)  # Wait 10 seconds and retry once
                        continue
                    else:
                        print(f"Imagen API call failed for prompt {i}: {e}")
                        if attempt == 0:
                            time.sleep(10)
                        else:
                            images.append(f"mock_image_{i}.png")
                except Exception as e:
                    print(f"Imagen API call failed for prompt {i}: {e}")
                    if attempt == 0:
                        time.sleep(10)
                    else:
                        images.append(f"mock_image_{i}.png")
            time.sleep(10) 
        logging.info(f"[IllustrationGeneratorAgent] Output images: {images}")
        if artifact is not None:
            artifact["illustrations"] = images
        return images

def slugify(value: str) -> str:
    import re
    value = value.lower()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    value = re.sub(r'-+', '-', value)
    value = value.strip('-')
    return value or 'book'

class BookAssemblerAgent(Agent):
    """Combines story & images into a PDF (reportlab)."""

    def run(
        self,
        scenes: list[str],
        illustrations: list[str],
        title: str = "Children's Book",
        *,
        artifact: dict | None = None,
    ):
        logging.info(f"[BookAssemblerAgent] Assembling PDF with {len(illustrations)} illustrations.")
        try:
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.pdfgen import canvas
            from reportlab.lib.utils import ImageReader
        except ImportError as exc:
            raise RuntimeError("Install reportlab to enable PDF output") from exc

        temp_dir = tempfile.gettempdir()
        pdf_filename = "PixieLabs Book.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)
        c = canvas.Canvas(pdf_path, pagesize=landscape(letter))
        width, height = landscape(letter)

        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(width / 2, height - 80, title)
        c.setFont("Helvetica", 14)
        c.drawCentredString(width / 2, height - 110, "Generated by ADK")
        c.showPage()

        for i, (scene, img_path) in enumerate(zip(scenes, illustrations)):
            c.setFont("Helvetica-Bold", 16)
        
            text_top_y = height - 60 
            left_margin = 72
            right_margin = 72
            max_text_width = width - left_margin - right_margin
            from reportlab.pdfbase.pdfmetrics import stringWidth
            words = scene.split()
            lines = []
            current_line = ""
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                if stringWidth(test_line, "Helvetica", 12) <= max_text_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            c.setFont("Helvetica", 12)
            text_y = text_top_y
            for line in lines:
                c.drawString(left_margin, text_y, line)
                text_y -= 16  
            # Calculate available space for image
            image_top = text_y - 10  
            image_bottom = 40  
            image_height = image_top - image_bottom
            image_left = left_margin
            image_right = width - right_margin
            image_width = image_right - image_left
            # Embed the corresponding illustration if it exists and is a real file
            if img_path and os.path.exists(img_path) and img_path.endswith('.png'):
                try:
                    img = ImageReader(img_path)
                    img_width, img_height = img.getSize()
                    # Fit image to the large rectangle (preserve aspect ratio)
                    scale = min(image_width / img_width, image_height / img_height, 1.0)
                    draw_width = img_width * scale
                    draw_height = img_height * scale
                    img_x = image_left + (image_width - draw_width) / 2
                    img_y = image_bottom + (image_height - draw_height) / 2
                    c.drawImage(img, img_x, img_y, draw_width, draw_height)
                    logging.info(f"[BookAssemblerAgent] Embedding image {i}: {img_path}")
                except Exception as e:
                    c.setFont("Helvetica-Oblique", 10)
                    c.drawString(left_margin, image_bottom + 10, f"[Failed to load illustration: {img_path}]")
            else:
                c.setFont("Helvetica-Oblique", 10)
                c.drawString(left_margin, image_bottom + 10, f"[Illustration: {img_path}]")
            # Draw page number at bottom right
            c.setFont("Helvetica", 10)
            page_num_text = f"Page {i + 1}"
            c.drawRightString(width - right_margin, 24, page_num_text)
            c.showPage()
        c.save()

        if artifact is not None:
            artifact["book"] = pdf_path
            artifact["book_filename"] = pdf_filename
        logging.info(f"[BookAssemblerAgent] PDF saved to: {pdf_path}")
        return pdf_path

# ────────────────────────────────  Workflow  ────────────────────────────────

class BookCreationWorkflow(SequentialAgent):
    """Coordinates all sub‑agents using ADK primitives."""

    def __init__(self):
        super().__init__(
            name="BookCreationWorkflow",
            sub_agents=[
                UserInputAgent(name="UserInputAgent"),
                StoryGeneratorAgent(name="StoryGeneratorAgent"),
                StoryElementsAgent(name="StoryElementsAgent"),
                CoherenceAgent(name="CoherenceAgent"),
                ParallelAgent(
                    name="ParallelMediaAgent",
                    sub_agents=[
                        IllustrationGeneratorAgent(name="IllustrationGeneratorAgent"),
                    ],
                ),
                BookAssemblerAgent(name="BookAssemblerAgent"),
            ],
        )

    def run(self, params: dict, session_id: str = None):
        memory: dict = {}
        artifact: dict = {}

        logging.info("[BookCreationWorkflow] Starting workflow")
        processed = self.sub_agents[0].run(params, memory=memory)
        logging.info("[BookCreationWorkflow] After UserInputAgent")
        story = self.sub_agents[1].run(processed, memory=memory)
        logging.info("[BookCreationWorkflow] After StoryGeneratorAgent")
        elements = self.sub_agents[2].run(story, memory=memory)
        logging.info("[BookCreationWorkflow] After StoryElementsAgent")
        prompts = self.sub_agents[3].run(story, processed, memory=memory)
        logging.info("[BookCreationWorkflow] After CoherenceAgent")
        illustrations = self.sub_agents[4].sub_agents[0].run(
            prompts, None, memory=memory, artifact=artifact
        )
        logging.info("[BookCreationWorkflow] After IllustrationGeneratorAgent")
        scenes = memory["scenes"] if "scenes" in memory else [story]
        character = elements.get("character") if isinstance(elements, dict) else processed.get("character_name", "A Friend")
        setting = elements.get("setting") if isinstance(elements, dict) else processed.get("setting", "A Magical Place")
        title = f"{character} in {setting}"
        pdf = self.sub_agents[5].run(scenes, illustrations, title=title, artifact=artifact)
        logging.info("[BookCreationWorkflow] After BookAssemblerAgent")
        return {
            "story": story,
            "elements": elements,
            "illustrations": illustrations,
            "book": pdf,
            "book_filename": "PixieLabs Book.pdf",
            "artifact": artifact,
        }

root_agent = BookCreationWorkflow()

if __name__ == "__main__":
    params = {}
    # Ask if user wants to randomize all fields first
    randomize_all = input("Randomize all fields? (y/N): ").strip().lower() == "y"
    params["randomize_all"] = randomize_all
    if not randomize_all:
        character_name = input("Enter the name of the main character (leave blank for random): ")
        if character_name:
            params["character_name"] = character_name

        animal = input("Enter the animal (e.g., rabbit, dog, fox) (leave blank for random): ")
        if animal:
            params["animal"] = animal

        gender = input("Enter the gender of the main character (male/female) (leave blank for random): ")
        if gender:
            params["gender"] = gender

        # Ask if user wants to add custom story elements
        add_custom = input("Do you want to add custom story elements? (y/N): ").strip().lower() == "y"
        if add_custom:
            custom_elements = input("Enter your custom story elements (e.g., 'a story about being a good older sibling and helping your family'): ").strip()
            if custom_elements:
                params["custom_elements"] = custom_elements
        else:
            setting = input("Enter the setting (leave blank for random): ")
            if setting:
                params["setting"] = setting

    result = root_agent.run(params)
    print("Story:", result["story"])
    print("Elements:", result["elements"])
    print("Illustrations:", result["illustrations"])
    print("Book PDF:", result["book"])
    print("Book filename:", result["book_filename"])
    print("Artifact:", result["artifact"]) 