# OAuth Provider Setup Guide

This guide explains how to set up OAuth authentication with various providers for the Advanced Authentication plugin.

## General Setup Process

For each OAuth provider, the general setup process is:

1. Create an application/project in the provider's developer console
2. Configure the OAuth credentials (Client ID, Client Secret)
3. Set up the correct redirect URIs
4. Configure the necessary scopes
5. Add the credentials to your environment variables

## GitHub OAuth Setup

1. **Register a new OAuth application**:
   - Go to [GitHub Developer Settings](https://github.com/settings/developers)
   - Click "New OAuth App"
   - Fill in the application details:
     - Application name: Your application name
     - Homepage URL: `https://your-domain.com`
     - Authorization callback URL: `https://your-domain.com/api/auth/oauth/github/callback`
   - Click "Register application"

2. **Get your credentials**:
   - Once registered, you'll see your Client ID
   - Generate a new Client Secret

3. **Set environment variables**:
   ```
   GITHUB_CLIENT_ID=your_client_id
   GITHUB_CLIENT_SECRET=your_client_secret
   ```

4. **Configure scopes**:
   The default scopes for GitHub OAuth are:
   - `read:user`
   - `user:email`

## Google OAuth Setup

1. **Create a project in Google Cloud Platform**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Navigate to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"

2. **Configure the OAuth consent screen**:
   - Set the application name, user support email, and developer contact information
   - Add the necessary scopes:
     - `https://www.googleapis.com/auth/userinfo.profile`
     - `https://www.googleapis.com/auth/userinfo.email`

3. **Create OAuth client ID**:
   - Application type: Web application
   - Name: Your application name
   - Authorized JavaScript origins: `https://your-domain.com`
   - Authorized redirect URIs: `https://your-domain.com/api/auth/oauth/google/callback`
   - Click "Create"

4. **Set environment variables**:
   ```
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   ```

## Microsoft OAuth Setup

1. **Register an application in Microsoft Azure Portal**:
   - Go to [Azure Portal](https://portal.azure.com/)
   - Navigate to "Azure Active Directory" > "App registrations"
   - Click "New registration"
   - Enter a name for your application
   - Set the redirect URI: `https://your-domain.com/api/auth/oauth/microsoft/callback`
   - Click "Register"

2. **Configure authentication**:
   - Under "Authentication", ensure "Access tokens" and "ID tokens" are checked

3. **Add API permissions**:
   - Navigate to "API permissions"
   - Add permissions for Microsoft Graph:
     - User.Read (delegated)
     - email (delegated)
     - profile (delegated)

4. **Create a client secret**:
   - Navigate to "Certificates & secrets"
   - Create a new client secret

5. **Set environment variables**:
   ```
   MICROSOFT_CLIENT_ID=your_client_id
   MICROSOFT_CLIENT_SECRET=your_client_secret
   ```

## Facebook OAuth Setup

1. **Create a Facebook app**:
   - Go to [Facebook Developers](https://developers.facebook.com/)
   - Click "My Apps" > "Create App"
   - Select the app type and fill in the details
   - Click "Create App"

2. **Set up Facebook Login**:
   - From the app dashboard, click "Add Product"
   - Select "Facebook Login" and choose "Web"
   - Enter your website URL
   - Set the Valid OAuth Redirect URIs: `https://your-domain.com/apiauth/oauth/facebook/callback`
   - Save changes

3. **Get app credentials**:
   - Go to "Settings" > "Basic"
   - Note your App ID and App Secret

4. **Set environment variables**:
   ```
   FACEBOOK_CLIENT_ID=your_app_id
   FACEBOOK_CLIENT_SECRET=your_app_secret
   ```

## Using the Configuration Script

The Advanced Authentication plugin includes a configuration script that helps you set up OAuth providers:

```bash
# List all supported providers
python -m app.plugins.advanced_auth.scripts.configure_oauth --list

# Configure a provider interactively
python -m app.plugins.advanced_auth.scripts.configure_oauth --provider github

# Configure a provider with command-line arguments
python -m app.plugins.advanced_auth.scripts.configure_oauth --provider google --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
```

## Testing OAuth Login

Once your OAuth providers are set up, you can test the login by:

1. Visiting your application login page
2. Clicking on the OAuth provider button (e.g., "Login with GitHub")
3. Authorizing the application on the provider's site
4. Being redirected back to your application

OAuth debugging endpoints are available at:
- `/apiauth/oauth/{provider}/login`
- `/apiauth/oauth/{provider}/callback`

## Troubleshooting

Common issues:

1. **Incorrect redirect URI**: Ensure the redirect URI exactly matches what's configured in the provider console
2. **Missing scopes**: Make sure you've requested the necessary scopes for user information
3. **Environment variables not set**: Verify that your environment variables are correctly set
4. **CORS issues**: For web applications, ensure your CORS configuration allows redirects from the OAuth provider

For more detailed provider-specific troubleshooting, consult the documentation for each provider.
