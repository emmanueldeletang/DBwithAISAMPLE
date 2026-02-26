"""
Azure Translator Service – translates text on the fly using Azure AI Translator.
Uses in-memory caching to avoid repeated API calls for the same text + language pair.
"""
import os
import requests
from typing import Optional


class AzureTranslatorService:
    """Thin wrapper around the Azure AI Translator REST API."""

    # Language codes that DON'T need translation (source language)
    SOURCE_LANG = 'en'

    def __init__(self):
        self.endpoint = os.getenv('AZURE_TRANSLATOR_ENDPOINT', '')
        self.key = os.getenv('AZURE_TRANSLATOR_KEY', '')
        self.region = os.getenv('AZURE_TRANSLATOR_REGION', '')
        self.api_url = f'{self.endpoint}/translator/text/v3.0/translate'
        # Dict-based cache keyed by (text, target_lang); supports direct insertion
        # from translate_bulk() so single-item calls hit the cache too.
        self._cache: dict[tuple[str, str], str] = {}

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def translate(self, text: str, target_lang: str) -> str:
        """Translate *text* to *target_lang*.

        Returns the original text when:
        - target_lang is the source language (en)
        - the text is empty / None
        - the API call fails (graceful degradation)
        """
        if not text or not text.strip():
            return text or ''
        if target_lang == self.SOURCE_LANG:
            return text

        # Use cached version
        return self._cached_translate(text.strip(), target_lang)

    def translate_dict(self, data: dict, fields: list, target_lang: str) -> dict:
        """Translate specific *fields* inside a dict, returning a **copy**."""
        if target_lang == self.SOURCE_LANG:
            return data
        result = dict(data)
        for field in fields:
            value = result.get(field)
            if value and isinstance(value, str):
                result[field] = self.translate(value, target_lang)
        return result

    def translate_list(self, items: list, fields: list, target_lang: str) -> list:
        """Translate specific *fields* for every dict in a list."""
        if target_lang == self.SOURCE_LANG:
            return items
        return [self.translate_dict(item, fields, target_lang) for item in items]

    # ------------------------------------------------------------------
    # Bulk translation (sends up to 100 texts per request for efficiency)
    # ------------------------------------------------------------------

    def translate_bulk(self, texts: list, target_lang: str) -> list:
        """Translate a list of strings in one API call (max 100 per batch).

        Returns translated strings in the same order.
        Falls back to original text on error.
        Results are stored in the shared cache so subsequent single-item
        calls for the same (text, lang) pair are served without an API call.
        """
        if not texts or target_lang == self.SOURCE_LANG:
            return texts

        results = []
        # Azure Translator allows max 100 items per request
        for i in range(0, len(texts), 100):
            batch = texts[i:i + 100]
            body = [{'Text': t} for t in batch]
            try:
                resp = requests.post(
                    self.api_url,
                    params={'api-version': '3.0', 'to': target_lang},
                    headers={
                        'Ocp-Apim-Subscription-Key': self.key,
                        'Ocp-Apim-Subscription-Region': self.region,
                        'Content-Type': 'application/json',
                    },
                    json=body,
                    timeout=10,
                )
                if resp.status_code == 200:
                    for item in resp.json():
                        translations = item.get('translations', [])
                        results.append(translations[0]['text'] if translations else batch[len(results) - i])
                else:
                    print(f"[Translator] bulk error {resp.status_code}: {resp.text[:200]}")
                    results.extend(batch)
            except Exception as e:
                print(f"[Translator] bulk exception: {e}")
                results.extend(batch)

        # Populate the cache so that single translate() calls are served
        # from cache without an extra API round-trip.
        for original, translated in zip(texts, results):
            self._cache[(original.strip(), target_lang)] = translated

        return results

    # ------------------------------------------------------------------
    # Internal – single-text call with dict-based cache
    # ------------------------------------------------------------------

    def _cached_translate(self, text: str, target_lang: str) -> str:
        """Return a cached translation or call the API and cache the result."""
        key = (text, target_lang)
        if key in self._cache:
            return self._cache[key]

        try:
            resp = requests.post(
                self.api_url,
                params={'api-version': '3.0', 'to': target_lang},
                headers={
                    'Ocp-Apim-Subscription-Key': self.key,
                    'Ocp-Apim-Subscription-Region': self.region,
                    'Content-Type': 'application/json',
                },
                json=[{'Text': text}],
                timeout=10,
            )
            if resp.status_code == 200:
                translations = resp.json()[0].get('translations', [])
                if translations:
                    result = translations[0]['text']
                    self._cache[key] = result
                    return result
            else:
                print(f"[Translator] error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[Translator] exception: {e}")
        return text  # Fallback to original

