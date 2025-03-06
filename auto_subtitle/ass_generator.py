from dataclasses import dataclass
from random import randint
from typing import List, Dict
import datetime

# ASS file section templates
ASS_SCRIPT_INFO_TEMPLATE = """[Script Info]
ScriptType: v4.00+
PlayResX: 320
PlayResY: 640
ScaledBorderAndShadow: yes"""

ASS_STYLES_SECTION_TEMPLATE = """
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{styles}"""

ASS_EVENTS_SECTION_TEMPLATE = """
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
{events}"""

ASS_FILE_TEMPLATE = """{script_info}
{styles_section}
{events_section}"""

# Event line templates
ASS_DIALOGUE_TEMPLATE = "Dialogue: 0,{start},{end},Default,,0,0,0,,{text}"
ASS_EFFECT_TEMPLATE = "{{\\t(0, {half}, \\fscx125\\fscy125)}}{{\\t({half}, {full}, \\fscx105\\fscy105)}}"
ASS_HIGHLIGHT_TEMPLATE = "{effect_template}{{\c{color}}}{word}{{\\r}}"

color_random = lambda: f"&H{randint(0, 255):02x}{randint(0, 255):02x}{randint(0, 255):02x}&"

@dataclass
class AssStyle:
    name: str
    font_name: str = "Arial"
    font_size: int = 32
    primary_color: str = "&H00FFFFFF"  # AABBGGRR format
    secondary_color: str = "&H000000FF"
    outline_color: str = "&H00000000"
    back_color: str = "&H00000000"
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikeout: bool = False
    scale_x: float = 100
    scale_y: float = 100
    spacing: float = 0
    angle: float = 0
    border_style: int = 1
    outline: float = 2.0
    shadow: float = 0
    alignment: int = 2  # 2 = bottom center
    margin_l: int = 10
    margin_r: int = 10
    margin_v: int = 160
    encoding: int = 1

    def to_ass_style(self) -> str:
        style_template = "Style: {name},{font_name},{font_size},{primary_color},{secondary_color},{outline_color},{back_color},{bold},{italic},{underline},{strikeout},{scale_x},{scale_y},{spacing},{angle},{border_style},{outline},{shadow},{alignment},{margin_l},{margin_r},{margin_v},{encoding}"
        
        return style_template.format(
            name=self.name,
            font_name=self.font_name,
            font_size=self.font_size,
            primary_color=self.primary_color,
            secondary_color=self.secondary_color,
            outline_color=self.outline_color,
            back_color=self.back_color,
            bold=1 if self.bold else 0,
            italic=1 if self.italic else 0,
            underline=1 if self.underline else 0,
            strikeout=1 if self.strikeout else 0,
            scale_x=self.scale_x,
            scale_y=self.scale_y,
            spacing=self.spacing,
            angle=self.angle,
            border_style=self.border_style,
            outline=self.outline,
            shadow=self.shadow,
            alignment=self.alignment,
            margin_l=self.margin_l,
            margin_r=self.margin_r,
            margin_v=self.margin_v,
            encoding=self.encoding
        )

class AssGenerator:
    def __init__(self):
        self.styles = {
            "default": AssStyle(
                name="Default",
                font_size=32,
                outline=2.0
            ),
            "highlight": AssStyle(
                name="Highlight",
                font_size=20,
                primary_color="&H0000FFFF",  # Yellow color for highlighted word
                outline_color="&H60000000",  # Semi-transparent black outline
                outline=2.0,
                bold=True
            )
        }

    def _format_time(self, seconds: float) -> str:
        """Convert seconds to ASS time format (H:MM:SS.cc)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        # Ensure milliseconds are always 3 digits
        centiseconds = int((seconds % 1) * 100)
        seconds = int(seconds)
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:03d}"

    def _time_to_centiseconds(self, time: float) -> int:
        """Convert time in seconds to centiseconds"""
        return int(time * 100)

    def _create_ass_header(self, style_name: str = "default") -> str:
        # Generate styles string
        styles_str = "\n".join(style.to_ass_style() for style in self.styles.values())
        
        # Fill in the templates
        styles_section = ASS_STYLES_SECTION_TEMPLATE.format(styles=styles_str)
        
        # Return the complete header (script info + styles section)
        return ASS_FILE_TEMPLATE.format(
            script_info=ASS_SCRIPT_INFO_TEMPLATE,
            styles_section=styles_section,
            events_section=ASS_EVENTS_SECTION_TEMPLATE.format(events="")
        )

    def generate_ass(self, segments: List[Dict], style_name: str = "default") -> str:
        header = self._create_ass_header(style_name)
        events = []
        
        # Preprocess segments to split long ones
        processed_segments = []
        for segment in segments:
            text = segment.get("text", "").strip()
            
            # If no words or text is short enough, keep as is
            if "words" not in segment or not segment["words"] or len(text) <= 20:
                processed_segments.append(segment)
                continue
            
            # Split long segments based on words
            words = segment["words"]
            current_segment = {
                "start": segment["start"],
                "text": "",
                "words": []
            }
            
            char_count = 0
            for i, word in enumerate(words):
                word_text = word.get("word", "").strip()
                if not word_text:
                    continue
                
                # Check if adding this word would exceed the limit
                if char_count + len(word_text) + (1 if char_count > 0 else 0) > 20 and char_count > 0:
                    # Finalize current segment
                    if current_segment["words"]:
                        # Set end time to the start time of the next word
                        current_segment["end"] = current_segment["words"][-1].get("end", segment["end"])
                        processed_segments.append(current_segment)
                    
                    # Start a new segment
                    current_segment = {
                        "start": word["start"],
                        "text": word_text,
                        "words": [word.copy()]
                    }
                    char_count = len(word_text)
                else:
                    # Add word to current segment
                    if char_count > 0:
                        current_segment["text"] += " " + word_text
                        char_count += len(word_text) + 1  # +1 for space
                    else:
                        current_segment["text"] = word_text
                        char_count = len(word_text)
                    
                    current_segment["words"].append(word.copy())
            
            # Add the last segment if it has content
            if current_segment["words"]:
                current_segment["end"] = segment["end"]
                processed_segments.append(current_segment)
        
        # Process the reorganized segments
        for segment in processed_segments:
            start_time = self._format_time(segment["start"])
            end_time = self._format_time(segment["end"])
            text = segment.get("text", "").strip()
            
            print(f"\nProcessing segment: {text}")
            
            # If word-level timing is available
            if "words" in segment and text:
                words = segment["words"]
                
                # If no words timing available, just show the text normally
                if not words:
                    line = ASS_DIALOGUE_TEMPLATE.format(start=start_time, end=end_time, text=text)
                    events.append(line)
                    continue
                
                # Get the full sentence first
                full_text = " ".join(w.get("word", "").strip() for w in words if w.get("word", "").strip())
                print(f"Full text: {full_text}")
                
                # Recalculate word timelines
                for i, word in enumerate(words):
                    word_text = word.get("word", "").strip()
                    if not word_text:
                        continue
                    
                    # Get the timing for this word
                    wordStartTime = word["start"]
                    # Calculate end time based on next word or segment end
                    wordEndTime = words[i + 1]["start"] if i < len(words) - 1 else segment["end"]
                    word["end"] = wordEndTime  # Store end time for future reference
                    
                    word_start = self._format_time(wordStartTime)
                    word_end = self._format_time(wordEndTime)
                    fullTime = self._time_to_centiseconds(min(wordEndTime - wordStartTime, 100))
                    halfTime = self._time_to_centiseconds(min(wordEndTime - wordStartTime, 100) / 2)
                    
                    # Split the full text into parts: before current word, current word, and after current word
                    words_list = full_text.split()
                    highlighted_text = []
                    
                    # Build the text with highlighting
                    for j, w in enumerate(words_list):
                        if j < i:
                            highlighted_text.append(w)
                        elif j == i:
                            effectStr = ASS_EFFECT_TEMPLATE.format(half=100,
                                                                 full=200)
                            highlighted_text.append(ASS_HIGHLIGHT_TEMPLATE
                                                 .format(word=w, 
                                                         effect_template=effectStr, 
                                                         color=color_random()))
                        else:
                            highlighted_text.append(w)
                    
                    final_text = " ".join(highlighted_text)
                    print(f"Generated line {i}: {final_text}")
                    
                    line = ASS_DIALOGUE_TEMPLATE.format(start=word_start, end=word_end, text=final_text)
                    events.append(line)
            
            else:
                # Regular subtitle without word timing
                line = ASS_DIALOGUE_TEMPLATE.format(start=start_time, end=end_time, text=text)
                events.append(line)
        
        # Replace the empty events section in the header with actual events
        events_section = ASS_EVENTS_SECTION_TEMPLATE.format(events="\n".join(events))
        return header.replace(ASS_EVENTS_SECTION_TEMPLATE.format(events=""), events_section)
