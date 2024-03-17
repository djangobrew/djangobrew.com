from os import getenv

from datetime import datetime
from django.http import Http404
from django.utils import timezone

import httpx

from django import template
from django.conf import settings
from django.core.cache import cache

register = template.Library()


DEFAULT_TIMEOUT = 60 * 5
CACHE_KEY_EPISODES = "django-brew:episodes"
CACHE_KEY_EPISODE = "django-brew:episode"


def _cache_it(key, value):
    if not settings.DEBUG:
        cache.set(key, value, timeout=DEFAULT_TIMEOUT)


@register.simple_tag
def get_episodes() -> list:
    podcast_id = getenv("BUZZSPROUT_PODCAST_ID")
    api_token = getenv("BUZZSPROUT_API_TOKEN")

    episodes = cache.get(CACHE_KEY_EPISODES, [])

    if episodes:
        return episodes

    try:
        url = f"https://www.buzzsprout.com/api/{podcast_id}/episodes.json"
        headers = {"Authorization": f"Token token={api_token}"}

        res = httpx.get(url, headers=headers)
        res.raise_for_status()

        data = res.json()

        for episode in data:
            if episode["private"] is False and episode["inactive_at"] is None:
                published_at = datetime.fromisoformat(episode["published_at"])

                if published_at <= timezone.now():
                    episode["player_url"] = episode["audio_url"].replace(".mp3", ".js")
                    episode["published_at"] = published_at
                    episodes.append(episode)
    except Exception as e:
        print(e)

    episodes = sorted(episodes, key=lambda e: e["published_at"], reverse=True)

    _cache_it(CACHE_KEY_EPISODES, episodes)

    return episodes


@register.simple_tag
def get_identifier(paths: list[str]) -> dict:
    slug = paths[1]
    first_dash = slug.index("-")

    return slug[0:first_dash]


@register.simple_tag
def get_episode(identifier: str) -> dict:
    cache_key = f"{CACHE_KEY_EPISODE}-{identifier}"

    if episode := cache.get(cache_key):
        return episode

    episodes = get_episodes()

    for e in episodes:
        if str(e["id"]) == identifier:
            episode = e
            _cache_it(CACHE_KEY_EPISODES, episode)

            break

    if not episode:
        raise Http404()

    return episode
