# AI/ML Integration Plugin

A powerful plugin for the Kaapi application that enables integration with various AI services, providing capabilities such as text analysis, sentiment evaluation, content generation, and personalized recommendations.

## Features

- **AI Service Provider Management**: Configure and manage multiple AI service providers (OpenAI, Azure OpenAI, Anthropic, Google AI, etc.).
- **Model Management**: Define and configure AI models from different providers with their capabilities and parameters.
- **Text Analysis**: Analyze text for sentiment, entities, categories, keywords, and language detection.
- **Content Generation**: Generate content using AI models for various use cases.
- **Recommendations**: Provide personalized content recommendations to users.
- **Usage Tracking**: Monitor and report on AI service usage across the application.

## Installation

1. Ensure that the plugin directory exists in your Kaapi application:

```bash
mkdir -p app/plugins/ai_integration
```

2. Copy the plugin files to the directory.

3. Install the required dependencies:

```bash
pip install openai anthropic google-generativeai langchain
```

4. Register the plugin in your main FastAPI application:

```python
from app.plugins.ai_integration.main import router as ai_router

app.include_router(ai_router)
```

## Configuration

The plugin requires configuration of AI service providers before use. The configuration includes API keys, base URLs, and provider-specific settings.

Example configuration for OpenAI:

```json
{
  "name": "OpenAI GPT",
  "provider_type": "openai",
  "is_default": true,
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-your-api-key",
  "config": {
    "organization": "org-id"
  }
}
```

## Core Concepts

### AI Providers

AI Providers represent the services that provide AI capabilities, such as OpenAI, Azure OpenAI, Anthropic, or Google AI. Each provider has its own API structure, authentication methods, and capabilities.

### AI Models

AI Models represent the specific models available from each provider. For example, GPT-4, Claude, or PaLM. Each model has its own capabilities, parameters, and pricing.

### Text Analysis

Text Analysis is the process of analyzing text to extract insights, including:
- **Sentiment Analysis**: Determining the emotional tone of text.
- **Entity Recognition**: Identifying and classifying entities mentioned in text.
- **Categorization**: Classifying text into predefined categories.
- **Keyword Extraction**: Identifying important terms in text.
- **Language Detection**: Determining the language of the text.

### Content Generation

Content Generation involves using AI models to generate text based on prompts, including:
- **Text Generation**: Creating new text based on a prompt.
- **Completions**: Completing text based on a partial input.
- **Chat**: Generating conversational responses.

### Recommendations

Recommendations involve using AI to suggest content to users based on their preferences, history, and behavior.

### Usage Tracking

Usage Tracking involves recording and reporting on the usage of AI services, including requests, tokens used, and costs.

## API Endpoints

### AI Providers

- `GET /ai/providers`: List AI providers
- `POST /ai/providers`: Create a new AI provider
- `GET /ai/providers/{provider_id}`: Get a specific AI provider
- `PUT /ai/providers/{provider_id}`: Update an AI provider
- `DELETE /ai/providers/{provider_id}`: Delete an AI provider

### AI Models

- `GET /ai/models`: List AI models
- `POST /ai/models`: Create a new AI model
- `GET /ai/models/{model_id}`: Get a specific AI model
- `PUT /ai/models/{model_id}`: Update an AI model
- `DELETE /ai/models/{model_id}`: Delete an AI model

### Text Analysis

- `POST /ai/text-analysis`: Analyze text
- `GET /ai/text-analysis/{entity_type}/{entity_id}`: Get analysis for an entity
- `DELETE /ai/text-analysis/{entity_type}/{entity_id}`: Delete analysis for an entity

### Content Generation

- `POST /ai/content`: Generate content
- `POST /ai/content/completion`: Complete text
- `POST /ai/content/chat`: Generate chat response

### Recommendations

- `POST /ai/recommendations`: Get recommendations
- `POST /ai/recommendations/{content_id}/feedback`: Provide feedback on recommendations
- `DELETE /ai/recommendations`: Clear recommendations

### Usage

- `GET /ai/usage`: Get usage records
- `GET /ai/usage/statistics`: Get usage statistics
- `DELETE /ai/usage`: Clear usage records

## Usage Examples

### Analyzing Text

```python
import requests

response = requests.post(
    "http://your-kaapi-app/ai/text-analysis",
    json={
        "text": "I really love this product! It's amazing and has solved all my problems.",
        "analysis_types": ["sentiment", "categories"],
        "entity_type": "review",
        "entity_id": 123
    }
)

result = response.json()
print(f"Sentiment: {result['sentiment']['label']} ({result['sentiment']['score']})")
print(f"Categories: {[c['name'] for c in result['categories']]}")
```

### Generating Content

```python
import requests

response = requests.post(
    "http://your-kaapi-app/ai/content",
    json={
        "prompt": "Write a product description for a smart home security camera.",
        "max_tokens": 500,
        "temperature": 0.8
    }
)

result = response.json()
print(result["generated_text"])
```

### Getting Recommendations

```python
import requests

response = requests.post(
    "http://your-kaapi-app/ai/recommendations",
    json={
        "user_id": 123,
        "content_type": "document",
        "limit": 5,
        "filters": {
            "categories": ["technical", "business"],
            "min_score": 0.7
        }
    }
)

result = response.json()
for item in result["items"]:
    print(f"Recommendation: Content ID {item['content_id']} (Score: {item['score']})")
```

## Frontend Integration

The AI Integration Plugin provides a RESTful API that can be integrated with any frontend framework. Here are some examples of how to integrate with common frontend frameworks:

### React Example

```jsx
import React, { useState } from 'react';
import axios from 'axios';

function TextAnalysisComponent() {
  const [text, setText] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const analyzeText = async () => {
    setLoading(true);
    try {
      const response = await axios.post('/api/ai/text-analysis', {
        text,
        analysis_types: ['sentiment', 'categories'],
      });
      setResult(response.data);
    } catch (error) {
      console.error('Error analyzing text:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Text Analysis</h2>
      <textarea 
        value={text} 
        onChange={(e) => setText(e.target.value)}
        placeholder="Enter text to analyze"
        rows={5}
        cols={50}
      />
      <button onClick={analyzeText} disabled={loading}>
        {loading ? 'Analyzing...' : 'Analyze Text'}
      </button>
      
      {result && (
        <div>
          <h3>Results:</h3>
          {result.sentiment && (
            <div>
              <h4>Sentiment:</h4>
              <p>Label: {result.sentiment.label}</p>
              <p>Score: {result.sentiment.score}</p>
            </div>
          )}
          {result.categories && (
            <div>
              <h4>Categories:</h4>
              <ul>
                {result.categories.map((category, index) => (
                  <li key={index}>
                    {category.name} ({(category.confidence * 100).toFixed(1)}%)
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default TextAnalysisComponent;
```

### Vue.js Example

```vue
<template>
  <div>
    <h2>Content Generation</h2>
    <div class="form-group">
      <label for="prompt">Prompt:</label>
      <textarea 
        id="prompt"
        v-model="prompt" 
        placeholder="Enter your prompt"
        rows="5"
        class="form-control"
      ></textarea>
    </div>
    
    <div class="form-group">
      <label for="temperature">Temperature:</label>
      <input 
        id="temperature"
        v-model.number="temperature" 
        type="range" 
        min="0" 
        max="1" 
        step="0.1"
        class="form-control"
      />
      <span>{{ temperature }}</span>
    </div>
    
    <button @click="generateContent" :disabled="loading" class="btn btn-primary">
      {{ loading ? 'Generating...' : 'Generate Content' }}
    </button>
    
    <div v-if="generatedContent" class="generated-content">
      <h3>Generated Content:</h3>
      <div class="content-box">{{ generatedContent }}</div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  data() {
    return {
      prompt: '',
      temperature: 0.7,
      generatedContent: null,
      loading: false
    };
  },
  methods: {
    async generateContent() {
      this.loading = true;
      try {
        const response = await axios.post('/api/ai/content', {
          prompt: this.prompt,
          temperature: this.temperature,
          max_tokens: 500
        });
        this.generatedContent = response.data.generated_text;
      } catch (error) {
        console.error('Error generating content:', error);
        this.$emit('error', 'Failed to generate content');
      } finally {
        this.loading = false;
      }
    }
  }
};
</script>

<style scoped>
.form-group {
  margin-bottom: 15px;
}
.form-control {
  width: 100%;
  padding: 8px;
}
.generated-content {
  margin-top: 20px;
}
.content-box {
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: #f9f9f9;
  white-space: pre-wrap;
}
</style>
```

## Security Considerations

1. **API Key Security**: API keys for AI providers should be stored securely and not exposed in client-side code.
2. **Rate Limiting**: Implement rate limiting to prevent abuse of AI services.
3. **Content Filtering**: Consider implementing content filtering to prevent generation or analysis of inappropriate content.
4. **Cost Management**: Set usage limits to prevent unexpected costs from third-party AI services.
5. **User Data Privacy**: Be transparent about how user data is used and ensure compliance with privacy regulations.

## Contributing

Contributions to the AI Integration Plugin are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This plugin is released under the same license as the Kaapi application.
