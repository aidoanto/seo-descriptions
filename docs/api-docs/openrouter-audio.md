---
title: Audio Inputs
subtitle: How to send audio files to OpenRouter models
headline: OpenRouter Audio Inputs | Complete Documentation
canonical-url: 'https://openrouter.ai/docs/features/multimodal/audio'
'og:site_name': OpenRouter Documentation
'og:title': OpenRouter Audio Inputs - Complete Documentation
'og:description': Send audio files to speech-capable models through the OpenRouter API.
'og:image':
  type: url
  value: >-
    https://openrouter.ai/dynamic-og?title=OpenRouter%20Audio%20Inputs&description=Send%20audio%20files%20to%20speech-capable%20models%20through%20the%20OpenRouter%20API.
'og:image:width': 1200
'og:image:height': 630
'twitter:card': summary_large_image
'twitter:site': '@OpenRouterAI'
noindex: false
nofollow: false
---

import { API_KEY_REF } from "../../../../imports/constants";

OpenRouter supports sending audio files to compatible models via the API. This guide will show you how to work with audio using our API.

**Note**: Audio files must be **base64-encoded** - direct URLs are not supported for audio content.

## Audio Inputs

Requests with audio files to compatible models are available via the `/api/v1/chat/completions` API with the `input_audio` content type. Audio files must be base64-encoded and include the format specification. Note that only models with audio processing capabilities will handle these requests.

You can search for models that support audio by filtering to audio input modality on our [Models page](/models?fmt=cards&input_modalities=audio).

### Sending Audio Files

Here's how to send an audio file for processing:

<Template data={{
  API_KEY_REF,
  MODEL: 'google/gemini-2.5-flash'
}}>
<CodeGroup>

```python
import requests
import json
import base64

def encode_audio_to_base64(audio_path):
    with open(audio_path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode('utf-8')

url = "https://openrouter.ai/api/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {API_KEY_REF}",
    "Content-Type": "application/json"
}

# Read and encode the audio file
audio_path = "path/to/your/audio.wav"
base64_audio = encode_audio_to_base64(audio_path)

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Please transcribe this audio file."
            },
            {
                "type": "input_audio",
                "input_audio": {
                    "data": base64_audio,
                    "format": "wav"
                }
            }
        ]
    }
]

payload = {
    "model": "{{MODEL}}",
    "messages": messages
}

response = requests.post(url, headers=headers, json=payload)
print(response.json())
```

```typescript
import fs from "fs/promises";

async function encodeAudioToBase64(audioPath: string): Promise<string> {
  const audioBuffer = await fs.readFile(audioPath);
  return audioBuffer.toString("base64");
}

// Read and encode the audio file
const audioPath = "path/to/your/audio.wav";
const base64Audio = await encodeAudioToBase64(audioPath);

const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${API_KEY_REF}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "{{MODEL}}",
    messages: [
      {
        role: "user",
        content: [
          {
            type: "text",
            text: "Please transcribe this audio file.",
          },
          {
            type: "input_audio",
            input_audio: {
              data: base64Audio,
              format: "wav",
            },
          },
        ],
      },
    ],
  }),
});

const data = await response.json();
console.log(data);
```

</CodeGroup>
</Template>

Supported audio formats are:

- `wav`
- `mp3`
