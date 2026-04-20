# AI Integration Frontend Examples

This directory contains example React components that showcase the integration of the AI capabilities into a frontend application. These components follow modern design principles including glassmorphism, gradient backgrounds, and interactive hover effects.

## Components

### AIAnalysisComponent

This component demonstrates how to use the Text Analysis endpoints to analyze text input and display the results in a visually appealing manner.

#### Features

- **Text input** with an "Analyze" button
- **Tabbed interface** to display different types of analysis:
  - Sentiment analysis with a visual meter
  - Category classification with bar charts
  - Entity recognition with colored badges
  - Keyword extraction with an interactive word cloud
- **Responsive design** that works well on both desktop and mobile
- **Modern UI elements**:
  - Glassmorphism effect for cards
  - Gradient backgrounds with subtle geometric shapes
  - Interactive hover effects on buttons and elements
  - Smooth animations for state transitions

#### Integration

To integrate this component into your Kaapi application:

1. Copy the `AIAnalysisComponent.js` and `AIAnalysisComponent.css` files to your frontend project.
2. Import the component where needed:

```jsx
import AIAnalysisComponent from './path/to/AIAnalysisComponent';

function YourPage() {
  return (
    <div>
      <h1>Your Page Title</h1>
      <AIAnalysisComponent />
    </div>
  );
}
```

3. Make sure your API routes match those used in the component or modify the component to use your specific API routes.

## Design Elements

These components incorporate the following modern design elements:

1. **Glassmorphism**: Translucent card elements with blur effects that create a sense of depth and layering.
2. **Gradient Backgrounds**: Rich blue/indigo gradient backgrounds that add visual interest and depth.
3. **Geometric Shapes**: Subtle blurred circles in the background that enhance the glassmorphism effect.
4. **Interactive Elements**: Buttons and cards with hover effects that provide visual feedback.
5. **"See More" Buttons**: Stylish buttons with hover animations for expanded functionality.

## Customization

You can customize the design elements by modifying the CSS variables in the `.css` files:

```css
:root {
  --primary-blue: #3B82F6;
  --primary-indigo: #6366F1;
  --primary-purple: #8B5CF6;
  --glass-background: rgba(255, 255, 255, 0.12);
  --glass-border: rgba(255, 255, 255, 0.18);
  --glass-shadow: rgba(31, 38, 135, 0.37);
}
```

## Additional Resources

For more information on how to use the AI Integration API endpoints, refer to the main [AI Integration README](/app/plugins/ai_integration/README.md).

## Required Dependencies

These components require the following dependencies:

- React 16.8+ (for Hooks support)
- Axios (for API requests)

To install them:

```bash
npm install axios
# or
yarn add axios
```
