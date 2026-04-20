/**
 * AI Text Analysis Component
 * 
 * A modern React component for text analysis that incorporates glassmorphism design,
 * gradient backgrounds, and interactive hover effects.
 */

import React, { useState } from 'react';
import axios from 'axios';
import './AIAnalysisComponent.css';

const AIAnalysisComponent = () => {
  const [text, setText] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('sentiment');

  const analyzeText = async () => {
    if (!text.trim()) return;
    
    setLoading(true);
    try {
      const response = await axios.post('/api/ai/text-analysis', {
        text,
        analysis_types: ['language', 'sentiment', 'entities', 'categories', 'keywords'],
      });
      setResult(response.data);
      setActiveTab('sentiment');
    } catch (error) {
      console.error('Error analyzing text:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderSentimentSection = () => {
    if (!result || !result.sentiment) return null;
    
    const { sentiment } = result;
    const sentimentColor = 
      sentiment.label === 'positive' ? '#4CAF50' : 
      sentiment.label === 'negative' ? '#F44336' : '#3F51B5';
    
    return (
      <div className="analysis-card sentiment-card">
        <h3>Sentiment Analysis</h3>
        <div className="sentiment-meter">
          <div 
            className="sentiment-indicator" 
            style={{ 
              left: `${(sentiment.score + 1) * 50}%`,
              backgroundColor: sentimentColor
            }}
          />
          <div className="sentiment-scale">
            <span>Negative</span>
            <span>Neutral</span>
            <span>Positive</span>
          </div>
        </div>
        <div className="sentiment-details">
          <p><strong>Label:</strong> {sentiment.label}</p>
          <p><strong>Score:</strong> {sentiment.score.toFixed(2)}</p>
          <p><strong>Confidence:</strong> {sentiment.confidence.toFixed(2)}</p>
        </div>
      </div>
    );
  };

  const renderCategoriesSection = () => {
    if (!result || !result.categories) return null;
    
    return (
      <div className="analysis-card categories-card">
        <h3>Categories</h3>
        <div className="categories-list">
          {result.categories.map((category, index) => (
            <div key={index} className="category-item">
              <div className="category-label">{category.name}</div>
              <div className="category-bar-container">
                <div 
                  className="category-bar" 
                  style={{ width: `${category.confidence * 100}%` }}
                />
              </div>
              <div className="category-percentage">{(category.confidence * 100).toFixed(1)}%</div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderEntitiesSection = () => {
    if (!result || !result.entities) return null;
    
    const entityTypeColors = {
      PERSON: '#E91E63',
      ORGANIZATION: '#2196F3',
      LOCATION: '#4CAF50',
      DATE: '#FF9800',
      EVENT: '#9C27B0',
      WORK_OF_ART: '#795548',
      CONSUMER_GOOD: '#607D8B',
      OTHER: '#9E9E9E'
    };
    
    return (
      <div className="analysis-card entities-card">
        <h3>Entities</h3>
        <div className="entities-list">
          {result.entities.map((entity, index) => (
            <div key={index} className="entity-item">
              <div 
                className="entity-type-badge"
                style={{ backgroundColor: entityTypeColors[entity.type] || entityTypeColors.OTHER }}
              >
                {entity.type}
              </div>
              <div className="entity-name">{entity.name}</div>
              <div className="entity-salience">{(entity.salience * 100).toFixed(1)}%</div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderKeywordsSection = () => {
    if (!result || !result.keywords) return null;
    
    return (
      <div className="analysis-card keywords-card">
        <h3>Keywords</h3>
        <div className="keywords-cloud">
          {result.keywords.map((keyword, index) => (
            <div 
              key={index} 
              className="keyword-item"
              style={{ 
                fontSize: `${1 + keyword.score}rem`,
                opacity: 0.5 + keyword.score * 0.5
              }}
            >
              {keyword.text}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="ai-analysis-container">
      <div className="geometric-background">
        <div className="geometric-shape shape1"></div>
        <div className="geometric-shape shape2"></div>
        <div className="geometric-shape shape3"></div>
      </div>
      
      <div className="glass-card input-card">
        <h2>AI Text Analysis</h2>
        <textarea 
          value={text} 
          onChange={(e) => setText(e.target.value)}
          placeholder="Enter text to analyze..."
          className="text-input"
          rows={6}
        />
        <button 
          onClick={analyzeText}
          className="analyze-button"
          disabled={loading}
        >
          {loading ? 'Analyzing...' : 'Analyze Text'}
        </button>
      </div>
      
      {result && (
        <div className="results-container">
          <div className="tabs-container">
            <button 
              className={`tab-button ${activeTab === 'sentiment' ? 'active' : ''}`}
              onClick={() => setActiveTab('sentiment')}
            >
              Sentiment
            </button>
            <button 
              className={`tab-button ${activeTab === 'categories' ? 'active' : ''}`}
              onClick={() => setActiveTab('categories')}
            >
              Categories
            </button>
            <button 
              className={`tab-button ${activeTab === 'entities' ? 'active' : ''}`}
              onClick={() => setActiveTab('entities')}
            >
              Entities
            </button>
            <button 
              className={`tab-button ${activeTab === 'keywords' ? 'active' : ''}`}
              onClick={() => setActiveTab('keywords')}
            >
              Keywords
            </button>
          </div>
          
          <div className="tab-content">
            {activeTab === 'sentiment' && renderSentimentSection()}
            {activeTab === 'categories' && renderCategoriesSection()}
            {activeTab === 'entities' && renderEntitiesSection()}
            {activeTab === 'keywords' && renderKeywordsSection()}
          </div>
          
          {result.language && (
            <div className="language-badge">
              Detected Language: <strong>{result.language.toUpperCase()}</strong>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AIAnalysisComponent;
