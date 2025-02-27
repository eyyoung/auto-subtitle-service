from dataclasses import dataclass
from typing import List, Dict
import datetime

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
    margin_v: int = 60
    encoding: int = 1

    def to_ass_style(self) -> str:
        return (
            f"Style: {self.name},"
            f"{self.font_name},"
            f"{self.font_size},"
            f"{self.primary_color},"
            f"{self.secondary_color},"
            f"{self.outline_color},"
            f"{self.back_color},"
            f"{1 if self.bold else 0},"
            f"{1 if self.italic else 0},"
            f"{1 if self.underline else 0},"
            f"{1 if self.strikeout else 0},"
            f"{self.scale_x},"
            f"{self.scale_y},"
            f"{self.spacing},"
            f"{self.angle},"
            f"{self.border_style},"
            f"{self.outline},"
            f"{self.shadow},"
            f"{self.alignment},"
            f"{self.margin_l},"
            f"{self.margin_r},"
            f"{self.margin_v},"
            f"{self.encoding}"
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
        header = [
            "[Script Info]",
            "ScriptType: v4.00+",
            "PlayResX: 320",
            "PlayResY: 640",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
        ]
        
        # Add all styles
        for style in self.styles.values():
            header.append(style.to_ass_style())
            
        header.extend(["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"])
        return "\n".join(header)

    def generate_ass(self, segments: List[Dict], style_name: str = "default") -> str:
        ass_content = [self._create_ass_header(style_name)]
        
        for segment in segments:
            start_time = self._format_time(segment["start"])
            end_time = self._format_time(segment["end"])
            text = segment.get("text", "").strip()
            
            print(f"\nProcessing segment: {text}")
            
            # If word-level timing is available
            if "words" in segment and text:
                words = segment["words"]
                
                # If no words timing available, just show the text normally
                if not words:
                    line = f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}"
                    ass_content.append(line)
                    continue

                # Get the full sentence first
                full_text = " ".join(w.get("word", "").strip() for w in words if w.get("word", "").strip())
                print(f"Full text: {full_text}")

                # Process each word
                for i, word in enumerate(words):
                    word_text = word.get("word", "").strip()
                    if not word_text:
                        continue
                    
                    # Get the timing for this word
                    word_start = self._format_time(word["start"])
                    word_end = self._format_time(words[i + 1]["start"] if i < len(words) - 1 else segment["end"])
                    
                    # Split the full text into parts: before current word, current word, and after current word
                    words_list = full_text.split()
                    current_word_pos = 0
                    highlighted_text = ""
                    
                    # Find the position of the current word
                    for j, w in enumerate(words_list):
                        if j < i:
                            highlighted_text += w + " "
                        elif j == i:
                            highlighted_text += "{\\1c&H0000FF}" + w + "{\\r}"
                            if j < len(words_list) - 1:
                                highlighted_text += " "
                        else:
                            highlighted_text += w
                            if j < len(words_list) - 1:
                                highlighted_text += " "
                    
                    print(f"Generated line {i}: {highlighted_text}")
                    
                    line = f"Dialogue: 0,{word_start},{word_end},Default,,0,0,0,,{highlighted_text}"
                    ass_content.append(line)

            else:
                # Regular subtitle without word timing
                line = f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}"
                ass_content.append(line)
        
        return "\n".join(ass_content)
