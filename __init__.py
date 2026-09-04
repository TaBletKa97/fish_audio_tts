import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from anki.utils import strip_html
from aqt import gui_hooks, mw
from aqt.qt import *
from aqt.sound import av_player
from aqt.utils import showInfo, showWarning, tooltip

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

        # 1. Читаем текущие настройки из config.json
        self.config = mw.addonManager.getConfig(__name__) or {}

        # 2. Создаем вертикальный контейнер для элементов
        layout = QVBoxLayout()

        # 3. Добавляем поле для ключа
        layout.addWidget(QLabel("API key:"))
        self.api_input = QLineEdit(self.config.get("api_key", ""))
        layout.addWidget(self.api_input)

        # 4. Добавляем поле для модели
        layout.addWidget(QLabel("Voice ID:"))
        self.model_input = QLineEdit(self.config.get("model_id", ""))
        layout.addWidget(self.model_input)

        # 5. Кнопка сохранения
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        self.setLayout(layout)

    def save_settings(self):
        # Сохраняем то, что ввел пользователь, обратно в файл
        self.config["api_key"] = self.api_input.text().strip()
        self.config["model_id"] = self.model_input.text().strip()
        mw.addonManager.writeConfig(__name__, self.config)

        # Закрываем окно
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
        self.setMinimumWidth(800)

        self.main_layout = QVBoxLayout()

        # Container for all rule rows
        self.rules_layout = QVBoxLayout()
        self.main_layout.addLayout(self.rules_layout)

        # Controls: Add Rule & Save buttons
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("+ Add Rule")
        self.add_btn.clicked.connect(self.add_rule_ui)
        btn_layout.addWidget(self.add_btn)

        self.save_btn = QPushButton("Save Rules")
        self.save_btn.clicked.connect(self.save_rules)
        btn_layout.addWidget(self.save_btn)

        self.main_layout.addLayout(btn_layout)
        self.setLayout(self.main_layout)

        # Fetch available field names for the current note type
        self.field_names = self.editor.note.keys()

        # Сначала всегда создаем и добавляем надпись
        self.empty_label = QLabel("To add a rule, click '+ Add Rule'")
        self.rules_layout.addWidget(self.empty_label)

        config = mw.addonManager.getConfig(__name__) or {}
        saved_rules = config.get("rules", {}).get(self.note_type_name, [])

        if saved_rules:
            # Если правила есть, скрываем надпись
            self.empty_label.hide()
            # Отрисовываем сохраненные правила как полноценные элементы интерфейса
            for rule in saved_rules:
                self.add_rule_ui(
                    rule.get("source"),
                    rule.get("dest"),
                    rule.get("selection_only", False),
                    rule.get("emotion", ""),
                    rule.get("custom_voice", ""),
                )

        self.rules_layout.addStretch()

    def add_rule_ui(
        self,
        source_val=None,
        dest_val=None,
        selection_val=False,
        emotion_val="",
        custom_voice_val="",
    ):
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

        row_data = {
            "layout": row_layout,
            "source": source_combo,
            "dest": dest_combo,
            "selection_only": selection_cb,
            "emotion": emotions_combo,
            "custom_voice": custom_voice_input,
        }
        self.rule_widgets.append(row_data)

        # 5. Delete Button
        delete_btn = QPushButton("🗑️")
        delete_btn.clicked.connect(lambda: self.delete_row(row_data))
        row_layout.addWidget(delete_btn)

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
                "custom_voice": row["custom_voice"].text(),
            }
            rules_list.append(rule)

        config["rules"][self.note_type_name] = rules_list
        mw.addonManager.writeConfig(__name__, config)

        tooltip("Rules saved successfully!")
        self.accept()


def show_rules_dialog(editor):
    # editor.widget - это родительское окно редактора, чтобы наше окно было поверх него
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
        return False, f"Ошибка API fish.audio: {error_body}"
    except Exception as e:
        return False, f"Внутренняя ошибка: {str(e)}"


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

    task_data = []
    for rule in rules:
        source_field = rule.get("source")
        dest_field = rule.get("dest")
        emotion = rule.get("emotion", "")
        selection_only = rule.get("selection_only", False)
        custom_voice = rule.get("custom_voice", "").strip()
        final_model_id = custom_voice if custom_voice else default_model_id

        if source_field not in note.keys() or dest_field not in note.keys():
            continue

        # 2. Проверяем: стоит ли галочка И не пустой ли выделенный текст
        if selection_only and selected_text.strip():
            clean_text = selected_text.strip()
        else:
            # 3. Во всех остальных случаях используем текст поля целиком
            clean_text = strip_html(note[source_field]).strip()

        # 4. Если в итоге текста нет вообще (поле пустое), переходим к следующему правилу
        if not clean_text:
            continue

        if emotion:
            clean_text = f"[{emotion}] {clean_text}"

        hash_text = hashlib.md5(clean_text.encode("utf-8")).hexdigest()[:16]
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
            # Аудио было на диске, но тега в поле не было (мы его добавили)
            editor.loadNote()
            tooltip(
                "Audio loaded from local cache (API skipped)!", parent=editor.widget
            )
        else:
            # Аудио на диске И тег уже прописан в поле (ничего менять не нужно)
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
        mw.progress.finish()
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
                av_player.play_file(path)
                time.sleep(1)
            else:
                err_msg = err
                break

        if changes_made:
            editor.loadNote()
            tooltip("Audio generated according to rules!", parent=editor.widget)
        if err_msg:
            showWarning(err_msg)

    mw.progress.start(label="Generating audio...")
    mw.taskman.run_in_background(bg_task, on_done)


def on_generate_tts(editor):
    note = editor.note
    note_type_name = note.model()["name"]

    config = mw.addonManager.getConfig(__name__) or {}
    rules = config.get("rules", {}).get(note_type_name, [])

    if not rules:
        showWarning(f"No rules found for '{note_type_name}'. Click 🐟⚙️ to add rules.")
        return

    # Запрашиваем выделенный текст через JavaScript.
    # Когда браузер вернет текст, он автоматически передаст его в process_tts_rules
    editor.web.evalWithCallback(
        "window.getSelection().toString();",
        lambda sel: process_tts_rules(editor, rules, sel),
    )


def setup_buttons(buttons, editor):
    # Add generate button in redactor
    btn = editor.addButton(
        icon=None,
        cmd="fish_tts",
        func=lambda editor=editor: on_generate_tts(editor),
        tip="Сгенерировать TTS через Fish.Audio (Ctrl+Shift+F)",
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


# Registrating button in redactor
gui_hooks.editor_did_init_buttons.append(setup_buttons)
