# Fish Audio TTS for Anki

Fish Audio TTS is an Anki add-on that generates high-quality text-to-speech audio using the Fish.Audio API. It allows users to define custom mapping rules for different note types directly within the Anki editor.

## Global Settings

Before generating audio, you must configure your Fish.Audio credentials. Navigate to **Tools -> Settings Fish TTS** from the main Anki window.

*   **API key:** Your personal authorization token from the Fish.Audio dashboard. (https://fish.audio/app/api-keys/)
*   **Voice ID:** The default model ID used when a specific rule does not define one. (https://fish.audio/app/discovery/)
*   **Random voice list:** A list of voices (with 'Enabled' checkbox, voice name/comment, and Voice ID) used when a rule has 'Use random voice' enabled. Disabled voices are kept in your list for future use without being picked during random generation.

## Configuring Rules

Rules are tied to specific Note Types (e.g., Basic, Cloze). In the Anki card editor, click the **🐟⚙️** button to open the rules configuration dialog. You can add multiple rules to process different fields simultaneously.

| Parameter | Description |
| :--- | :--- |
| **Source** | The Anki field containing the text you want to synthesize. |
| **Dest** | The Anki field where the generated `[sound:...]` tag will be assigned. |
| **Selection only** | If checked, the add-on only reads the text currently highlighted by the user. If the highlight is empty, it falls back to reading the entire source field. |
| **Emotion** | Prepends a specific emotional modifier to the text prompt. Supported emotions include *happy, sad, angry, excited, calm, nervous, confident, surprised, satisfied, delighted, scared, worried, upset, frustrated, depressed, empathetic, embarrassed, disgusted, moved, proud, relaxed, grateful, curious, and sarcastic*. |
| **Custom Voice** | An optional Voice ID that overrides the global default voice for this specific rule. |
| **Use random voice** | If checked, picks a random voice from your configured Random voice list for each request of this rule. |

## Generating Audio

Once rules are set, click the **🐟** button in the editor or use the **Ctrl+Shift+F** keyboard shortcut to generate the audio. 

*   **Background Processing:** Network requests run in a background thread with a progress indicator, ensuring the Anki UI remains responsive during downloads.
*   **Smart Caching:** The add-on hashes the text payload to track exactly what has been generated. If you request audio for a text string that already exists in your local Anki media folder, the add-on skips the API request and instantly assigns the cached local file, saving your API tokens.
*   **Auto-Playback:** Generated or cached audio files automatically play back in the editor for quick review.