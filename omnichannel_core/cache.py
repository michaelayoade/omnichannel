"""
Cache utilities for the omnichannel application.
Implements caching decorators and patterns for common use cases.
"""

from functools import wraps
from django.core.cache import cache
from django.conf import settings
import hashlib
import json


def generate_cache_key(prefix, *args, **kwargs):
    """
    Generate a consistent cache key from prefix and arguments.
    """
    key_parts = [str(prefix)]
    
    # Add positional args
    if args:
        key_parts.extend([str(arg) for arg in args])
    
    # Add keyword args, sorted by key
    if kwargs:
        kwargs_str = json.dumps(kwargs, sort_keys=True)
        key_parts.append(kwargs_str)
    
    # Join and hash to ensure key length constraints
    key = "_".join(key_parts)
    if len(key) > 200:  # Redis keys should be reasonable in length
        key_hash = hashlib.md5(key.encode()).hexdigest()
        key = f"{prefix}_{key_hash}"
    
    return key


def cached_response(timeout=300, key_prefix=None):
    """
    Decorator for caching view responses.
    
    Args:
        timeout: Cache expiration time in seconds
        key_prefix: Prefix for the cache key
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Skip cache for non-GET requests
            if request.method != 'GET':
                return view_func(self, request, *args, **kwargs)
            
            # Generate cache key
            prefix = key_prefix or f"{view_func.__module__}.{view_func.__name__}"
            cache_key = generate_cache_key(prefix, 
                                          request.path, 
                                          request.query_params.dict(), 
                                          user_id=request.user.id if request.user.is_authenticated else 'anonymous')
            
            # Try to get from cache
            response_data = cache.get(cache_key)
            
            if response_data is None:
                # Execute view if not in cache
                response = view_func(self, request, *args, **kwargs)
                
                # Cache the response
                if hasattr(response, 'data'):
                    cache.set(cache_key, response.data, timeout)
                
                return response
            
            # Recreate response from cached data
            return self.get_paginated_response(response_data) if hasattr(self, 'paginate_queryset') else response_data
        
        return wrapper
    
    return decorator


def invalidate_model_cache(model_name, obj_id=None):
    """
    Invalidate cache entries related to a specific model
    
    Args:
        model_name: The name of the model
        obj_id: Optional specific object ID to invalidate
    """
    if obj_id:
        cache_pattern = f"{model_name}_{obj_id}*"
    else:
        cache_pattern = f"{model_name}_*"
        
    # Delete matching keys
    if hasattr(cache, 'delete_pattern'):
        # Redis backend supports pattern deletion
        cache.delete_pattern(cache_pattern)
    else:
        # For other backends, can't do much about patterns
        pass


class CacheControlMiddleware:
    """
    Middleware to set cache control headers.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Set cache headers for API responses
        if request.path.startswith('/api/') and request.method == 'GET':
            if getattr(settings, 'API_CACHE_SECONDS', None):
                timeout = settings.API_CACHE_SECONDS
                response['Cache-Control'] = f'public, max-age={timeout}'
        
        # Set cache headers for static assets
        elif request.path.startswith('/static/') or request.path.startswith('/media/'):
            timeout = 60 * 60 * 24 * 7  # 1 week
            response['Cache-Control'] = f'public, max-age={timeout}'
            
        return response
