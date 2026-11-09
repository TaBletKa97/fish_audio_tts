import hashlib
import html
import json
import os
import random
import re
import time
import urllib.error
import urllib.request

from aqt import gui_hooks, mw
from aqt.qt import *
from aqt.sound import av_player
from aqt.utils import showInfo, showWarning, tooltip


def strip_html(text):
    """Return text with HTML tags removed and entities decoded."""
    return html.unescape(re.sub(r"<[^>]+>", "", text))


EMOTIONS = [
    "happy",
    "sad",
    "angry",
    "excited",
    "calm",
    "nervous",
    "confident",
    "surprised",
    "satisfied",
    "delighted",
    "scared",
    "worried",
    "upset",
    "frustrated",
    "depressed",
    "empathetic",
    "embarrassed",
    "disgusted",
    "moved",
    "proud",
    "relaxed",
    "grateful",
    "curious",
    "sarcastic",
]


# GENERAL SETTINGS
class FishSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings Fish TTS")
        self.setMinimumWidth(600)
        self.resize(650, 480)

        # 1. Read current settings from config.json
        self.config = mw.addonManager.getConfig(__name__) or {}
        self.voice_rows = []

        # 2. Create vertical container for elements
        layout = QVBoxLayout()

        # 3. Add API key field
        layout.addWidget(QLabel("API key:"))
        self.api_input = QLineEdit(self.config.get("api_key", ""))
        layout.addWidget(self.api_input)

        # 4. Add model field
        layout.addWidget(QLabel("Voice ID (Default):"))
        self.model_input = QLineEdit(self.config.get("model_id", ""))
        layout.addWidget(self.model_input)

        layout.addSpacing(10)

        # 5. Random voices section
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<b>Random voice list</b>"))
        header_layout.addStretch()

        add_voice_btn = QPushButton("+ Add voice to list")
        add_voice_btn.clicked.connect(lambda: self.add_voice_row())
        header_layout.addWidget(add_voice_btn)
        layout.addLayout(header_layout)

        # Scroll area for voice list
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.voices_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)

        # Load saved voices
        saved_voices = self.config.get("random_voices", [])
        for v in saved_voices:
            if isinstance(v, dict):
                self.add_voice_row(v.get("name", ""), v.get("id", ""))
            elif isinstance(v, str):
                self.add_voice_row("", v)

        self.voices_layout.addStretch()

        # 6. Save button
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        self.setLayout(layout)

    def add_voice_row(self, name="", voice_id=""):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 2, 0, 2)

        row_layout.addWidget(QLabel("Name:"))
        name_input = QLineEdit(name)
        name_input.setPlaceholderText("Voice name / comment")
        row_layout.addWidget(name_input)

        row_layout.addWidget(QLabel("Voice ID:"))
        id_input = QLineEdit(voice_id)
        id_input.setPlaceholderText("Model ID")
        row_layout.addWidget(id_input)

        del_btn = QPushButton("❌")
        del_btn.setStyleSheet("min-width: 30px; padding: 2px 6px;")
        del_btn.setToolTip("Delete voice")
        row_layout.addWidget(del_btn)

        row_data = {
            "widget": row_widget,
            "name": name_input,
            "id": id_input,
        }
        del_btn.clicked.connect(lambda: self.delete_voice_row(row_data))
        self.voice_rows.append(row_data)

        count = self.voices_layout.count()
        if count > 0 and self.voices_layout.itemAt(count - 1).spacerItem():
            self.voices_layout.insertWidget(count - 1, row_widget)
        else:
            self.voices_layout.addWidget(row_widget)

    def delete_voice_row(self, row_data):
        if row_data in self.voice_rows:
            self.voice_rows.remove(row_data)
        row_data["widget"].deleteLater()

    def save_settings(self):
        # Save user inputs back to file
        self.config["api_key"] = self.api_input.text().strip()
        self.config["model_id"] = self.model_input.text().strip()

        voices_list = []
        for row in self.voice_rows:
            name = row["name"].text().strip()
            vid = row["id"].text().strip()
            if name or vid:
                voices_list.append({"name": name, "id": vid})
        self.config["random_voices"] = voices_list

        mw.addonManager.writeConfig(__name__, self.config)

        # Close dialog
        self.accept()


def show_settings():
    dialog = FishSettingsDialog(mw)
    dialog.exec()


action = QAction("Settings Fish TTS", mw)
action.triggered.connect(show_settings)
mw.form.menuTools.addAction(action)


# -------------------------------------------------------------------
# RULES SETTINGS
# -------------------------------------------------------------------
class FishRulesDialog(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.rule_widgets = []

        # Getting card type
        self.note_type_name = editor.note.model()["name"]

        self.setWindowTitle(f"Rules Fish TTS: {self.note_type_name}")
        self.setMinimumWidth(920)

        self.main_layout = QVBoxLayout()

        # Scroll area for rule rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        rules_container = QWidget()
        self.rules_layout = QVBoxLayout(rules_container)
        scroll.setWidget(rules_container)
        self.main_layout.addWidget(scroll)

        # Controls: Add Rule & Save buttons
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("+ Add Rule")
        self.add_btn.clicked.connect(lambda: self.add_rule_ui())
        btn_layout.addWidget(self.add_btn)

        self.save_btn = QPushButton("Save Rules")
        self.save_btn.clicked.connect(self.save_rules)
        btn_layout.addWidget(self.save_btn)

        self.main_layout.addLayout(btn_layout)
        self.setLayout(self.main_layout)

        # Fetch available field names for the current note type
        self.field_names = self.editor.note.keys()

        # Create and add empty label first
        self.empty_label = QLabel("To add a rule, click '+ Add Rule'")
        self.rules_layout.addWidget(self.empty_label)

        config = mw.addonManager.getConfig(__name__) or {}
        saved_rules = config.get("rules", {}).get(self.note_type_name, [])

        if saved_rules:
            # If rules exist, hide the label
            self.empty_label.hide()
            # Render saved rules as UI elements
            for rule in saved_rules:
                self.add_rule_ui(
                    rule.get("source"),
                    rule.get("dest"),
                    rule.get("selection_only", False),
                    rule.get("emotion", ""),
                    rule.get("custom_voice", ""),
                    rule.get("use_random_voice", False),
                )

        self.rules_layout.addStretch()

    def add_rule_ui(
        self,
        source_val=None,
        dest_val=None,
        selection_val=False,
        emotion_val="",
        custom_voice_val="",
        use_random_voice_val=False,
        *args,
    ):
        if not isinstance(source_val, str):
            source_val = None

        self.empty_label.hide()

        """Creates a new horizontal row with rule settings"""
        row_layout = QHBoxLayout()

        # 1. Source Field
        row_layout.addWidget(QLabel("Source:"))
        source_combo = QComboBox()
        source_combo.addItems(self.field_names)
        if source_val:
            source_combo.setCurrentText(source_val)
        row_layout.addWidget(source_combo)

        # 2. Destination Field
        row_layout.addWidget(QLabel("Dest:"))
        dest_combo = QComboBox()
        dest_combo.addItems(self.field_names)
        if dest_val:
            dest_combo.setCurrentText(dest_val)
        row_layout.addWidget(dest_combo)

        # 3. Checkbox: Selected text only
        selection_cb = QCheckBox("Selection only")
        if selection_val:
            selection_cb.setChecked(True)
        row_layout.addWidget(selection_cb)

        # 4. Emotion
        row_layout.addWidget(QLabel("Emotion:"))
        emotions_combo = QComboBox()
        emotions_combo.addItems(EMOTIONS)
        if emotion_val:
            emotions_combo.setCurrentText(emotion_val)
        row_layout.addWidget(emotions_combo)

        # 5. Custom Voice
        row_layout.addWidget(QLabel("Custom Voice:"))
        custom_voice_input = QLineEdit()
        custom_voice_input.setPlaceholderText("Model ID")
        if custom_voice_val:
            custom_voice_input.setText(custom_voice_val)
        row_layout.addWidget(custom_voice_input)

        # 6. Checkbox: Use random voice
        random_voice_cb = QCheckBox("Use random voice")
        if use_random_voice_val:
            random_voice_cb.setChecked(True)
            custom_voice_input.setEnabled(False)
        random_voice_cb.toggled.connect(
            lambda checked, inp=custom_voice_input: inp.setEnabled(not checked)
        )
        row_layout.addWidget(random_voice_cb)

        # 7. Delete Button
        delete_btn = QPushButton("🗑️")
        row_layout.addWidget(delete_btn)

        row_data = {
            "layout": row_layout,
            "source": source_combo,
            "dest": dest_combo,
            "selection_only": selection_cb,
            "emotion": emotions_combo,
            "custom_voice": custom_voice_input,
            "use_random_voice": random_voice_cb,
        }
        self.rule_widgets.append(row_data)

        delete_btn.clicked.connect(lambda: self.delete_row(row_data))

        count = self.rules_layout.count()
        if count > 0 and self.rules_layout.itemAt(count - 1).spacerItem():
            self.rules_layout.insertLayout(count - 1, row_layout)
        else:
            self.rules_layout.addLayout(row_layout)

    def delete_row(self, row_data):
        if row_data in self.rule_widgets:
            self.rule_widgets.remove(row_data)

        layout = row_data["layout"]
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        layout.deleteLater()

        if not self.rule_widgets:
            self.empty_label.show()

    def save_rules(self):
        config = mw.addonManager.getConfig(__name__) or {}
        if "rules" not in config:
            config["rules"] = {}

        rules_list = []

        for row in self.rule_widgets:
            rule = {
                "source": row["source"].currentText(),
                "dest": row["dest"].currentText(),
                "selection_only": row["selection_only"].isChecked(),
                "emotion": row["emotion"].currentText(),
                "custom_voice": row["custom_voice"].text().strip(),
                "use_random_voice": row["use_random_voice"].isChecked(),
            }
            rules_list.append(rule)

        config["rules"][self.note_type_name] = rules_list
        mw.addonManager.writeConfig(__name__, config)

        tooltip("Rules saved successfully!")
        self.accept()


def show_rules_dialog(editor):
    # editor.widget is editor parent window so dialog stays on top
    dialog = FishRulesDialog(editor, parent=editor.widget)
    dialog.exec()


# -------------------------------------------------------------------
# ADDING AUDIO
# -------------------------------------------------------------------


def fetch_audio(text, output_path, model_id):
    config = mw.addonManager.getConfig(__name__) or {}
    api_key = config.get("api_key", "")
    url = "https://api.fish.audio/v1/tts"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "model": "s2.1-pro-free",
    }

    data = {"text": text, "reference_id": model_id, "format": "mp3", "mp3_bitrate": 64}

    req = urllib.request.Request(
        url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response, open(output_path, "wb") as f:
            f.write(response.read())
        return True, ""
    except urllib.error.URLError as e:
        # Reading error body, if server provided a text
        error_body = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
        return False, f"Fish.audio API error: {error_body}"
    except Exception as e:
        return False, f"Internal error: {str(e)}"


def process_tts_rules(editor, rules, selected_text):

    config = mw.addonManager.getConfig(__name__) or {}
    if not config.get("api_key"):
        showWarning(
            "First define API key (https://fish.audio/app/api-keys/). Tools -> Settings Fish TTS"
        )
        return
    if not config.get("model_id"):
        showWarning(
            "First define Voice 'Model ID' (https://fish.audio/app/discovery/). Tools -> Settings Fish TTS"
        )
        return

    note = editor.note

    default_model_id = config.get("model_id", "")
    cached_changes = False

    # Extract valid random voices
    random_voices = config.get("random_voices", [])
    valid_random_voice_ids = []
    for v in random_voices:
        if isinstance(v, dict):
            vid = v.get("id", "").strip()
        elif isinstance(v, str):
            vid = v.strip()
        else:
            vid = ""
        if vid:
            valid_random_voice_ids.append(vid)

    task_data = []
    for rule in rules:
        source_field = rule.get("source")
        dest_field = rule.get("dest")
        emotion = rule.get("emotion", "")
        selection_only = rule.get("selection_only", False)
        custom_voice = rule.get("custom_voice", "").strip()
        use_random_voice = rule.get("use_random_voice", False)

        if use_random_voice:
            if not valid_random_voice_ids:
                showWarning(
                    "A rule has 'Use random voice' enabled, but the random voice list is empty.\n"
                    "Please add voices in Tools -> Settings Fish TTS."
                )
                return
            final_model_id = random.choice(valid_random_voice_ids)
        elif custom_voice:
            final_model_id = custom_voice
        else:
            final_model_id = default_model_id

        if source_field not in note.keys() or dest_field not in note.keys():
            continue

        # 2. Check: selection only checked AND selection is not empty
        if selection_only and selected_text.strip():
            clean_text = selected_text.strip()
        else:
            # 3. Otherwise use the entire field text
            clean_text = strip_html(note[source_field]).strip()

        # 4. If field is empty, proceed to next rule
        if not clean_text:
            continue

        if emotion:
            clean_text = f"[{emotion}] {clean_text}"

        hash_payload = (
            f"{clean_text}_{final_model_id}"
            if (use_random_voice or custom_voice)
            else clean_text
        )
        hash_text = hashlib.md5(hash_payload.encode("utf-8")).hexdigest()[:16]
        filename = f"fish_audio_{hash_text}.mp3"
        media_dir = mw.col.media.dir()
        output_path = os.path.join(media_dir, filename)

        sound_tag = f" [sound:{filename}]"
        if os.path.exists(output_path):
            if sound_tag not in note[dest_field]:
                note[dest_field] = sound_tag
                cached_changes = True
            continue

        task_data.append(
            (clean_text, output_path, dest_field, filename, final_model_id)
        )

    if not task_data:
        if cached_changes:
            # Audio was already on disk, but sound tag was missing from the field (added it)
            editor.loadNote()
            tooltip(
                "Audio loaded from local cache (API skipped)!", parent=editor.widget
            )
        else:
            # Audio is on disk AND sound tag already exists in field (nothing to change)
            tooltip(
                "Audio already exists in the field (Skipped)!", parent=editor.widget
            )
        return

    if not task_data:
        return

    # 2. Execute network requests in the background
    def bg_task():
        results = []
        for text, path, dest, fname, model_id in task_data:
            success, err = fetch_audio(text, path, model_id)
            results.append((success, err, path, dest, fname))
            if not success:
                break
        return results

    # 3. Update the note and UI on the main thread
    def on_done(future):
        try:
            results = future.result()
        except Exception as e:
            showWarning(f"Task failed: {str(e)}")
            return

        changes_made = False
        err_msg = ""

        for success, err, path, dest, fname in results:
            if success:
                # Appending the sound tag prevents overwriting existing text
                editor.note[dest] = f" [sound:{fname}]"
                changes_made = True
            else:
                err_msg = err
                break

        if changes_made:
            editor.loadNote()
            tooltip("Audio generated according to rules!", parent=editor.widget)
            for success, err, path, dest, fname in results:
                if success:
                    av_player.insert_file(path)
        if err_msg:
            showWarning(err_msg)

    mw.taskman.run_in_background(bg_task, on_done)
    tooltip("Generating audio in the background...", parent=editor.widget)


def on_generate_tts(editor):
    note = editor.note
    note_type_name = note.model()["name"]

    config = mw.addonManager.getConfig(__name__) or {}
    rules = config.get("rules", {}).get(note_type_name, [])

    if not rules:
        showWarning(f"No rules found for '{note_type_name}'. Click 🐟⚙️ to add rules.")
        return

    # Request selected text via JavaScript.
    # When browser returns text, it is passed to process_tts_rules
    editor.web.evalWithCallback(
        "window.getSelection().toString();",
        lambda sel: process_tts_rules(editor, rules, sel),
    )


def setup_buttons(buttons, editor):
    # Add generate button in editor
    btn = editor.addButton(
        icon=None,
        cmd="fish_tts",
        func=lambda editor=editor: on_generate_tts(editor),
        tip="Generate TTS via Fish.Audio (Ctrl+Shift+F)",
        keys="Ctrl+Shift+F",
        label="🐟",
    )
    buttons.append(btn)

    # Add rules button
    btn_rules = editor.addButton(
        icon=None,
        cmd="fish_tts_rules",
        func=lambda editor=editor: show_rules_dialog(editor),
        tip="Setup fish tts rules",
        keys=None,
        label="🐟⚙️",
    )
    buttons.append(btn_rules)

    return buttons


# Register buttons in editor
gui_hooks.editor_did_init_buttons.append(setup_buttons)
