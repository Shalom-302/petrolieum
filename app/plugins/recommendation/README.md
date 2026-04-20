# Recommendation Plugin

A comprehensive hybrid recommendation system plugin for KAAPI applications that provides personalized content recommendations using multiple algorithms.

## Overview

This plugin implements a complete recommendation system with multiple algorithms:

1. **Collaborative Filtering**
   - User-based: Recommends items liked by similar users
   - Item-based: Recommends items similar to those the user has liked

2. **Matrix Factorization**
   - SVD (Singular Value Decomposition) for latent factor modeling
   - Efficient for large-scale recommendation systems

3. **Content-based Filtering**
   - Recommends items with similar features to those the user likes
   - Uses text analysis and feature extraction

4. **Hybrid Recommendations**
   - Combines multiple algorithms with weighted scoring
   - Optimizes for both relevance and diversity

5. **Basic Algorithms**
   - Popularity-based: Recommends trending or most popular items
   - Random: Provides serendipitous discovery

## Features

- **Personalized Recommendations**: Tailored to each user's preferences and behavior
- **Real-time Feedback**: Captures user interactions to continuously improve recommendations
- **Performance Monitoring**: Tracks metrics like click-through rate to evaluate algorithm effectiveness
- **Scheduled Model Training**: Automatically refreshes recommendation models to incorporate new data
- **Standardized Security**: Uses the application's core security infrastructure for data protection
- **Scalable Architecture**: Designed to handle large volumes of users and items

## API Endpoints

The plugin provides several API endpoints:

### Recommendation Endpoints

- `POST /recommend/items`: Get personalized recommendations for a user
- `POST /recommend/similar`: Find items similar to a specified item
- `GET /recommend/trending`: Get trending items based on recent popularity

### Feedback Endpoints

- `POST /feedback/record`: Record user feedback on recommendations
- `POST /feedback/batch`: Submit multiple feedback entries at once
- `POST /feedback/preferences`: Update user preferences for recommendation tuning

### Admin Endpoints

- `POST /admin/train`: Trigger training of recommendation models
- `GET /admin/status`: Get system status and performance metrics
- `DELETE /admin/purge_old_data`: Remove old data to maintain performance
- `POST /admin/reset_recommendations`: Reset recommendation history

## Integration

To integrate this plugin into your KAAPI application:

1. Add the plugin to your main application file:

```python
from app.plugins.recommendation.main import recommendation_plugin

# In the application configuration function
recommendation_plugin.init_app(app, prefix="/api/recommendation")
```

2. Run database migrations to create the necessary tables:

```bash
alembic revision --autogenerate -m "Add recommendation system tables"
alembic upgrade head
```

3. Start recording user interactions with your content:

```python
# Example: Recording a user viewing an article
response = requests.post(
    "http://your-api/api/recommendation/feedback/record",
    json={
        "user_id": 123,
        "item_id": 456,
        "feedback_type": "view",
        "context": "homepage"
    }
)
```

4. Retrieve recommendations for users:

```python
# Example: Getting personalized recommendations
response = requests.post(
    "http://your-api/api/recommendation/recommend/items",
    json={
        "user_id": 123,
        "count": 10,
        "algorithm": "hybrid"
    }
)
recommendations = response.json()
```

## Configuration

The plugin can be configured through environment variables:

- `RECOMMENDATION_CACHE_TTL`: Time-to-live for cached recommendations (default: 3600 seconds)
- `RECOMMENDATION_DEFAULT_ALGO`: Default algorithm to use (default: "hybrid")
- `RECOMMENDATION_MODEL_REFRESH_HOUR`: Hour of day to refresh models (default: 3)

## Security

This plugin follows the standardized security approach used throughout the KAAPI application:

- Sensitive user data is encrypted using the application's encryption handler
- API rate limiting is applied to prevent abuse
- Secure logging practices protect user privacy
- All database interactions follow security best practices

## Performance Considerations

- Recommendations are cached for optimal performance
- Heavy model training tasks run in the background on a schedule
- The system automatically purges old data to maintain database performance
- API endpoints are optimized for fast response times

## Requirements

- Python 3.8+
- FastAPI
- SQLAlchemy
- NumPy
- Pandas
- SciPy
- Scikit-learn

## License

This plugin is part of the KAAPI framework and is subject to the same license terms.
