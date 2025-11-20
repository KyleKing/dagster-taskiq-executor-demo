from __future__ import annotations

from collections.abc import Callable

try:
    from moto.aiobotocore import patch as aiobotocore_patch
except ImportError:
    # Fallback to custom patch if moto's aiobotocore patch is not available
    from unittest.mock import MagicMock

    import aiobotocore.awsrequest
    import aiobotocore.endpoint
    import aiohttp
    import aiohttp.client_reqrep
    import aiohttp.typedefs
    import botocore.awsrequest

    class _MockAWSResponse(aiobotocore.awsrequest.AioAWSResponse):
        def __init__(self, response: botocore.awsrequest.AWSResponse) -> None:  # type: ignore[override]
            self._moto_response = response
            self.status_code = response.status_code
            self.raw = _MockHttpClientResponse(response)

        @property
        def content(self) -> bytes:
            return self._moto_response.content

        @property
        def text(self) -> str:
            return self._moto_response.text

        @property
        def headers(self):
            return self._moto_response.headers

    class _MockHttpClientResponse(aiohttp.client_reqrep.ClientResponse):
        def __init__(self, response: botocore.awsrequest.AWSResponse) -> None:
            self.response = response
            self.content = MagicMock(aiohttp.StreamReader)

            async def _read(_: int = -1) -> bytes:
                return response.content

            self.content.read = _read  # type: ignore[assignment]

        @property
        def raw_headers(self) -> aiohttp.typedefs.RawHeaders:
            return tuple(
                (str(key).encode("utf-8"), str(value).encode("utf-8")) for key, value in self.response.headers.items()
            )

    def apply_aiobotocore_patch() -> Callable[[], None]:
        """Patch aiobotocore to operate against moto-backed AWS stubs."""
        original_convert = aiobotocore.endpoint.convert_to_response_dict

        def _patched_convert(
            http_response: aiobotocore.awsrequest.AWSResponse,
            operation_model,
        ):
            return original_convert(_MockAWSResponse(http_response), operation_model)

        aiobotocore.endpoint.convert_to_response_dict = _patched_convert

        def _restore() -> None:
            aiobotocore.endpoint.convert_to_response_dict = original_convert

        return _restore

else:

    def apply_aiobotocore_patch() -> Callable[[], None]:
        """Use moto's built-in aiobotocore patch."""
        aiobotocore_patch.apply_patches()
        return aiobotocore_patch.unapply_patches
