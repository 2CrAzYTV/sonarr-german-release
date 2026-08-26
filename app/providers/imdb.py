import asyncio
import json
from dataclasses import dataclass

import boto3

from ..config import settings


@dataclass
class ProviderStatus:
    name: str
    configured: bool
    active: bool
    note: str


class ImdbProvider:
    """Official IMDb API provider via AWS Data Exchange.

    No webpage scraping is used. Requests are sent through boto3's
    DataExchange client, which handles AWS SigV4 signing.
    """

    name = "imdb_de"

    def status(self) -> ProviderStatus:
        missing = settings.imdb_missing_settings
        if not missing:
            return ProviderStatus(
                name=self.name,
                configured=True,
                active=True,
                note="Offizielle IMDb API vollständig konfiguriert",
            )

        return ProviderStatus(
            name=self.name,
            configured=False,
            active=False,
            note="Fehlt: " + ", ".join(missing),
        )

    def _client(self):
        kwargs = {
            "service_name": "dataexchange",
            "region_name": settings.imdb_aws_region,
            "aws_access_key_id": settings.imdb_aws_access_key_id,
            "aws_secret_access_key": settings.imdb_aws_secret_access_key,
        }
        if settings.imdb_aws_session_token:
            kwargs["aws_session_token"] = settings.imdb_aws_session_token
        return boto3.client(**kwargs)

    def _query_sync(self, query: str) -> dict:
        if not settings.imdb_api_configured:
            raise RuntimeError(
                "IMDb API ist nicht vollständig konfiguriert: "
                + ", ".join(settings.imdb_missing_settings)
            )

        response = self._client().send_api_asset(
            DataSetId=settings.imdb_data_set_id,
            RevisionId=settings.imdb_revision_id,
            AssetId=settings.imdb_asset_id,
            Method="POST",
            Path="/v1",
            Body=json.dumps({"query": query}),
            RequestHeaders={
                "x-api-key": settings.imdb_api_key,
                "Content-Type": "application/json",
            },
        )

        body = response.get("Body") or "{}"
        payload = json.loads(body)
        if payload.get("errors"):
            messages = "; ".join(
                error.get("message", "IMDb GraphQL error")
                for error in payload["errors"]
            )
            raise RuntimeError(messages)
        return payload

    async def query(self, query: str) -> dict:
        return await asyncio.to_thread(self._query_sync, query)

    async def probe(self, imdb_id: str) -> dict:
        """Small official API request used to verify the subscription."""
        safe_id = imdb_id.replace('"', "")
        query = f'''\
query {{
  title(id: "{safe_id}") {{
    id
    titleText {{ text }}
    titleType {{ text canHaveEpisodes }}
  }}
}}
'''
        payload = await self.query(query)
        return (payload.get("data") or {}).get("title") or {}

    async def episode_ids(self, imdb_series_id: str, first: int = 100) -> list[dict]:
        """Fetch IMDb episode IDs for a series using the documented episodes field.

        This intentionally returns IDs/titles only. Country-specific release-date
        extraction will be added only after the subscribed schema is validated.
        """
        safe_id = imdb_series_id.replace('"', "")
        first = max(1, min(first, 250))
        after = None
        result: list[dict] = []

        while True:
            after_arg = f', after: "{after}"' if after else ""
            query = f'''\
query {{
  title(id: "{safe_id}") {{
    episodes {{
      episodes(first: {first}{after_arg}) {{
        edges {{
          node {{
            id
            titleText {{ text }}
          }}
        }}
        pageInfo {{ endCursor hasNextPage }}
      }}
    }}
  }}
}}
'''
            payload = await self.query(query)
            title = (payload.get("data") or {}).get("title") or {}
            connection = ((title.get("episodes") or {}).get("episodes") or {})
            for edge in connection.get("edges") or []:
                node = edge.get("node") or {}
                if node.get("id"):
                    result.append(
                        {
                            "id": node["id"],
                            "title": ((node.get("titleText") or {}).get("text")),
                        }
                    )

            page_info = connection.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")
            if not after:
                break

        return result
