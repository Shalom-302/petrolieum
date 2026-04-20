"""
Service Worker Builder for PWA Support

This module generates a dynamic service worker script based on configuration.
The service worker handles caching strategies and offline capabilities.
"""


def generate_service_worker(config):
    """
    Generate a service worker script based on configuration.
    
    Args:
        config (dict): Configuration dictionary with cache settings
            - cache_version: Version string for cache
            - cache_name: Name of the cache
            - urls_to_cache: List of URLs to precache
            - offline_fallback: Path to offline fallback page
            - dynamic_cache_enabled: Whether to enable dynamic caching
            - cache_strategies: Dictionary mapping route patterns to cache strategies
    
    Returns:
        str: Complete service worker JavaScript code
    """
    cache_version = config.get('cache_version', 'v1')
    cache_name = config.get('cache_name', 'kaapi-pwa-cache')
    urls_to_cache = config.get('urls_to_cache', [])
    offline_fallback = config.get('offline_fallback', '/offline.html')
    dynamic_cache_enabled = config.get('dynamic_cache_enabled', True)
    cache_strategies = config.get('cache_strategies', {})
    
    # Build service worker JavaScript
    sw_js = f"""
// Kaapi PWA Service Worker - {cache_version}
const CACHE_NAME = '{cache_name}';
const URLS_TO_CACHE = {str(urls_to_cache).replace("'", '"')};
const OFFLINE_FALLBACK = '{offline_fallback}';

// Installation event - precache static assets
self.addEventListener('install', event => {{
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {{
                console.log('Service Worker: Caching files');
                return cache.addAll(URLS_TO_CACHE);
            }})
            .then(() => self.skipWaiting())
    );
}});

// Activation event - clean up old caches
self.addEventListener('activate', event => {{
    const cacheWhitelist = [CACHE_NAME];
    
    event.waitUntil(
        caches.keys().then(cacheNames => {{
            return Promise.all(
                cacheNames.map(cacheName => {{
                    if (!cacheWhitelist.includes(cacheName)) {{
                        console.log('Service Worker: Deleting old cache', cacheName);
                        return caches.delete(cacheName);
                    }}
                }})
            );
        }})
        .then(() => self.clients.claim())
    );
}});

// Fetch event - handle network requests with appropriate caching strategy
self.addEventListener('fetch', event => {{
    const request = event.request;
    
    // Skip non-GET requests
    if (request.method !== 'GET') return;
    
    // Skip cross-origin requests
    if (!request.url.startsWith(self.location.origin)) return;
    
    // Determine the caching strategy based on URL pattern
    const strategy = determineCachingStrategy(request.url);
    
    switch (strategy) {{
        case 'cache-first':
            event.respondWith(cacheFirstStrategy(request));
            break;
        case 'network-first':
            event.respondWith(networkFirstStrategy(request));
            break;
        case 'stale-while-revalidate':
            event.respondWith(staleWhileRevalidateStrategy(request));
            break;
        default:
            event.respondWith(networkFirstStrategy(request));
    }}
}});

// Push notification event
self.addEventListener('push', event => {{
    if (!event.data) return;
    
    try {{
        const data = event.data.json();
        console.log('Push notification received:', data);
        
        const options = {{
            body: data.message || 'New notification',
            icon: data.icon || '/static/icons/icon-192x192.png',
            badge: data.badge,
            tag: data.tag,
            data: data.data || {{}},
            actions: data.actions || [],
            vibrate: [100, 50, 100],
            timestamp: Date.now()
        }};
        
        event.waitUntil(
            self.registration.showNotification(data.title || 'Kaapi Notification', options)
        );
    }} catch (error) {{
        console.error('Error showing notification:', error);
    }}
}});

// Notification click event
self.addEventListener('notificationclick', event => {{
    event.notification.close();
    
    // Handle notification click - navigating to a specific URL if provided
    const targetUrl = event.notification.data.url || '/';
    
    event.waitUntil(
        clients.matchAll({{type: 'window'}})
            .then(clientList => {{
                // If a window client is already open, focus it
                for (const client of clientList) {{
                    if (client.url === targetUrl && 'focus' in client) {{
                        return client.focus();
                    }}
                }}
                
                // Otherwise, open a new window
                if (clients.openWindow) {{
                    return clients.openWindow(targetUrl);
                }}
            }})
    );
}});

// CACHING STRATEGIES

// Cache-First Strategy
// Try the cache first, falling back to network if not cached
function cacheFirstStrategy(request) {{
    return caches.match(request)
        .then(cachedResponse => {{
            if (cachedResponse) {{
                return cachedResponse;
            }}
            
            return fetch(request)
                .then(networkResponse => {{
                    // Cache the response for future
                    if ({str(dynamic_cache_enabled).lower()} && networkResponse.ok) {{
                        return caches.open(CACHE_NAME)
                            .then(cache => {{
                                cache.put(request, networkResponse.clone());
                                return networkResponse;
                            }});
                    }}
                    
                    return networkResponse;
                }})
                .catch(() => {{
                    // If both cache and network fail, show offline page for HTML requests
                    if (request.headers.get('Accept').includes('text/html')) {{
                        return caches.match(OFFLINE_FALLBACK);
                    }}
                    
                    // For other resources, just fail
                    return new Response('Network error happened', {{
                        status: 408,
                        headers: {{ 'Content-Type': 'text/plain' }}
                    }});
                }});
        }});
}}

// Network-First Strategy
// Try the network first, falling back to cache if network fails
function networkFirstStrategy(request) {{
    return fetch(request)
        .then(networkResponse => {{
            // Cache the response for future
            if ({str(dynamic_cache_enabled).lower()} && networkResponse.ok) {{
                caches.open(CACHE_NAME)
                    .then(cache => {{
                        cache.put(request, networkResponse.clone());
                    }});
            }}
            
            return networkResponse;
        }})
        .catch(() => {{
            return caches.match(request)
                .then(cachedResponse => {{
                    if (cachedResponse) {{
                        return cachedResponse;
                    }}
                    
                    // If both network and cache fail, show offline page for HTML requests
                    if (request.headers.get('Accept').includes('text/html')) {{
                        return caches.match(OFFLINE_FALLBACK);
                    }}
                    
                    // For other resources, just fail
                    return new Response('Network error happened', {{
                        status: 408,
                        headers: {{ 'Content-Type': 'text/plain' }}
                    }});
                }});
        }});
}}

// Stale-While-Revalidate Strategy
// Return cached version immediately, then update cache in background
function staleWhileRevalidateStrategy(request) {{
    return caches.match(request)
        .then(cachedResponse => {{
            const fetchPromise = fetch(request)
                .then(networkResponse => {{
                    if ({str(dynamic_cache_enabled).lower()} && networkResponse.ok) {{
                        caches.open(CACHE_NAME)
                            .then(cache => {{
                                cache.put(request, networkResponse.clone());
                            }});
                    }}
                    return networkResponse;
                }})
                .catch(() => {{
                    // If network fails and we're requesting HTML, show offline page
                    if (request.headers.get('Accept').includes('text/html')) {{
                        return caches.match(OFFLINE_FALLBACK);
                    }}
                    
                    throw new Error('Network request failed');
                }});
            
            // Return the cached response immediately, or wait for the network response
            return cachedResponse || fetchPromise;
        }});
}}

// Determine which caching strategy to use based on URL patterns
function determineCachingStrategy(url) {{
    const cache_strategies = {str(cache_strategies).replace("'", '"') if cache_strategies else '{}'};
    
    // Default strategies by content type/path pattern
    if (url.match(/\\.(css|js|woff2?|ttf|eot)$/i)) {{
        return 'cache-first'; // Static resources
    }}
    
    if (url.match(/\\.(jpg|jpeg|png|gif|svg|webp)$/i)) {{
        return 'stale-while-revalidate'; // Images
    }}
    
    if (url.includes('/api/')) {{
        return 'network-first'; // API calls
    }}
    
    // Check custom configured strategies
    for (const [pattern, strategy] of Object.entries(cache_strategies)) {{
        if (url.includes(pattern)) {{
            return strategy;
        }}
    }}
    
    // Default to network-first for everything else
    return 'network-first';
}}
"""
    return sw_js
