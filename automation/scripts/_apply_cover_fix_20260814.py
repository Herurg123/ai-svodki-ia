from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(rel: str, old: str, new: str) -> None:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected block not found in {rel}: {old[:100]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one block in {rel}, got {text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(rel: str, marker: str, addition: str) -> None:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n", encoding="utf-8")


# 1. Image generator: provenance ID is optional; actual image request ID remains required.
replace_once(
    "automation/scripts/generate_image_preview.py",
    '''class ImageGenerationError(RuntimeError):\n    """A safe error from the one-shot image generation stage."""\n''',
    '''class ImageGenerationError(RuntimeError):\n    """A safe error from the one-shot image generation stage."""\n\n    stage = "image_generation"\n\n\nclass ImagePreflightError(ImageGenerationError):\n    """The local artifact/request contract failed before any Images API call."""\n\n    stage = "image_preflight"\n\n\nclass ImageApiTransportError(ImageGenerationError):\n    """The Images API could not be reached."""\n\n    stage = "image_api_transport"\n\n\nclass ImageApiHttpError(ImageGenerationError):\n    """The Images API returned an HTTP error."""\n\n    stage = "image_api_http"\n\n    def __init__(\n        self,\n        message: str,\n        *,\n        http_status: int | None = None,\n        openai_request_id: str | None = None,\n        api_error_type: str | None = None,\n        api_error_code: str | None = None,\n    ) -> None:\n        super().__init__(message)\n        self.http_status = http_status\n        self.openai_request_id = openai_request_id\n        self.api_error_type = api_error_type\n        self.api_error_code = api_error_code\n\n\nclass ImageApiResponseError(ImageGenerationError):\n    """The Images API returned an unusable successful response."""\n\n    stage = "image_api_response"\n''',
)

for old, new in [
    ('raise ImageGenerationError("Images API должен вернуть ровно один data[] item")', 'raise ImageApiResponseError("Images API должен вернуть ровно один data[] item")'),
    ('raise ImageGenerationError("Images API не вернул data[0].b64_json")', 'raise ImageApiResponseError("Images API не вернул data[0].b64_json")'),
    ('raise ImageGenerationError("Images API вернул некорректный base64") from exc', 'raise ImageApiResponseError("Images API вернул некорректный base64") from exc'),
    ('raise ImageGenerationError("Images API вернул данные без сигнатуры PNG")', 'raise ImageApiResponseError("Images API вернул данные без сигнатуры PNG")'),
]:
    replace_once("automation/scripts/generate_image_preview.py", old, new)

replace_once(
    "automation/scripts/generate_image_preview.py",
    '''def default_transport(\n    *,\n    api_url: str,\n    api_key: str,\n    request_payload: dict[str, Any],\n    timeout_seconds: int,\n) -> dict[str, Any]:\n    body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")\n    request = urllib.request.Request(\n        api_url,\n        data=body,\n        method="POST",\n        headers={\n            "Authorization": f"Bearer {api_key}",\n            "Content-Type": "application/json",\n            "User-Agent": "ai-svodki-image-preview/1.0",\n        },\n    )\n    try:\n        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:\n            response_body = response.read()\n    except urllib.error.HTTPError as exc:\n        error_body = exc.read().decode("utf-8", errors="replace")[:4000]\n        raise ImageGenerationError(\n            f"Images API HTTP {exc.code}: {error_body}"\n        ) from exc\n    except urllib.error.URLError as exc:\n        raise ImageGenerationError(\n            f"Images API network error: {exc.reason}"\n        ) from exc\n    try:\n        payload = json.loads(response_body.decode("utf-8"))\n    except (UnicodeDecodeError, json.JSONDecodeError) as exc:\n        raise ImageGenerationError("Images API вернул некорректный JSON") from exc\n    if not isinstance(payload, dict):\n        raise ImageGenerationError("Images API response должен быть JSON-объектом")\n    return payload\n''',
    '''def default_transport(\n    *,\n    api_url: str,\n    api_key: str,\n    request_payload: dict[str, Any],\n    timeout_seconds: int,\n) -> dict[str, Any]:\n    body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")\n    request = urllib.request.Request(\n        api_url,\n        data=body,\n        method="POST",\n        headers={\n            "Authorization": f"Bearer {api_key}",\n            "Content-Type": "application/json",\n            "User-Agent": "ai-svodki-image-preview/1.1",\n        },\n    )\n    try:\n        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:\n            response_body = response.read()\n            http_status = getattr(response, "status", None)\n            openai_request_id = str(response.headers.get("x-request-id") or "").strip() or None\n    except urllib.error.HTTPError as exc:\n        error_body = exc.read().decode("utf-8", errors="replace")[:4000]\n        openai_request_id = str(\n            (exc.headers.get("x-request-id") if exc.headers is not None else "") or ""\n        ).strip() or None\n        api_error_type = None\n        api_error_code = None\n        api_message = error_body\n        try:\n            error_payload = json.loads(error_body)\n            error_object = error_payload.get("error") if isinstance(error_payload, dict) else None\n            if isinstance(error_object, dict):\n                api_message = str(error_object.get("message") or error_body)\n                api_error_type = str(error_object.get("type") or "").strip() or None\n                api_error_code = str(error_object.get("code") or "").strip() or None\n        except json.JSONDecodeError:\n            pass\n        raise ImageApiHttpError(\n            f"Images API HTTP {exc.code}: {api_message}",\n            http_status=exc.code,\n            openai_request_id=openai_request_id,\n            api_error_type=api_error_type,\n            api_error_code=api_error_code,\n        ) from exc\n    except urllib.error.URLError as exc:\n        raise ImageApiTransportError(\n            f"Images API network error: {exc.reason}"\n        ) from exc\n    try:\n        payload = json.loads(response_body.decode("utf-8"))\n    except (UnicodeDecodeError, json.JSONDecodeError) as exc:\n        raise ImageApiResponseError("Images API вернул некорректный JSON") from exc\n    if not isinstance(payload, dict):\n        raise ImageApiResponseError("Images API response должен быть JSON-объектом")\n    payload["_transport"] = {\n        "http_status": http_status,\n        "openai_request_id": openai_request_id,\n    }\n    return payload\n''',
)

replace_once(
    "automation/scripts/generate_image_preview.py",
    ''') -> str:\n    value = str(source_manifest.get("editorial_request_id") or "").strip()''',
    ''') -> str | None:\n    value = str(source_manifest.get("editorial_request_id") or "").strip()''',
)
replace_once(
    "automation/scripts/generate_image_preview.py",
    '''    if value:\n        return value\n    raise ImageGenerationError("Не удалось определить editorial request ID")\n''',
    '''    if value:\n        return value\n    return None\n''',
)

# Clear preflight classification for the most important local guards.
for old, new in [
    ('raise ImageGenerationError("Image request не активен или имеет неверный mode")', 'raise ImagePreflightError("Image request не активен или имеет неверный mode")'),
    ('raise ImageGenerationError("OPENAI_API_KEY отсутствует")', 'raise ImagePreflightError("OPENAI_API_KEY отсутствует")'),
    ('raise ImageGenerationError(\n            f"OPENAI_IMAGE_MODEL не совпадает с config: {model!r} != {target_model!r}"\n        )', 'raise ImagePreflightError(\n            f"OPENAI_IMAGE_MODEL не совпадает с config: {model!r} != {target_model!r}"\n        )'),
    ('raise ImageGenerationError("Image request_id отсутствует")', 'raise ImagePreflightError("Image request_id отсутствует")'),
]:
    replace_once("automation/scripts/generate_image_preview.py", old, new)

replace_once(
    "automation/scripts/generate_image_preview.py",
    '''    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")\n    response_payload = transport(\n        api_url=api_url,\n        api_key=api_key,\n        request_payload=api_request,\n        timeout_seconds=timeout_seconds,\n    )\n    image_bytes, safe_response = parse_response_payload(response_payload)\n''',
    '''    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")\n    print("Image preflight: ok; calling Images API once.")\n    response_payload = transport(\n        api_url=api_url,\n        api_key=api_key,\n        request_payload=api_request,\n        timeout_seconds=timeout_seconds,\n    )\n    transport_metadata = response_payload.get("_transport")\n    if not isinstance(transport_metadata, dict):\n        transport_metadata = {}\n    image_bytes, safe_response = parse_response_payload(response_payload)\n''',
)

replace_once(
    "automation/scripts/generate_image_preview.py",
    '''        "request_id": request_id,\n        "target_model": target_model,''',
    '''        "request_id": request_id,\n        "image_request_id": request_id,\n        "target_model": target_model,''',
)
replace_once(
    "automation/scripts/generate_image_preview.py",
    '''        "editorial_request_id": editorial_request_id,\n        "network_used": True,''',
    '''        "editorial_request_id": editorial_request_id,\n        "source_editorial_request_id": editorial_request_id,\n        "network_used": True,''',
)
replace_once(
    "automation/scripts/generate_image_preview.py",
    '''        "request_id": request_id,\n        "source": "openai_images_api",''',
    '''        "request_id": request_id,\n        "image_request_id": request_id,\n        "source_editorial_request_id": editorial_request_id,\n        "source": "openai_images_api",''',
)
replace_once(
    "automation/scripts/generate_image_preview.py",
    '''        "endpoint": "/v1/images/generations",\n        "request": {''',
    '''        "endpoint": "/v1/images/generations",\n        "http_status": transport_metadata.get("http_status"),\n        "openai_request_id": transport_metadata.get("openai_request_id"),\n        "source_editorial_request_id": editorial_request_id,\n        "request": {''',
)

replace_once(
    "automation/scripts/generate_image_preview.py",
    '''    except Exception as exc:\n        error = {\n            "status": "error",\n            "stage": "image_api_preview",\n            "error_type": type(exc).__name__,\n            "message": str(exc),\n            "api_key_stored": False,\n            "failed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),\n        }\n        try:\n            write_json(output_dir / "image-api-error.json", error)\n        except OSError:\n            pass\n        print(f"Image API preview failed: {exc}", file=sys.stderr)\n        return 1\n''',
    '''    except Exception as exc:\n        stage = str(getattr(exc, "stage", "image_generation"))\n        error = {\n            "status": "error",\n            "stage": stage,\n            "error_type": type(exc).__name__,\n            "message": str(exc),\n            "api_attempted": stage.startswith("image_api_"),\n            "http_status": getattr(exc, "http_status", None),\n            "openai_request_id": getattr(exc, "openai_request_id", None),\n            "api_error_type": getattr(exc, "api_error_type", None),\n            "api_error_code": getattr(exc, "api_error_code", None),\n            "api_key_stored": False,\n            "failed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),\n        }\n        try:\n            write_json(output_dir / "image-api-error.json", error)\n        except OSError:\n            pass\n        print(f"Image stage failed [{stage}]: {exc}", file=sys.stderr)\n        return 1\n''',
)

# 2. Regression tests, including the exact missing editorial-ID failure class.
replace_once(
    "automation/tests/test_image_preview.py",
    '''import base64\nimport importlib.util\nimport json\nimport shutil\nimport sys\nimport tempfile\nimport unittest\nfrom pathlib import Path\n''',
    '''import base64\nimport importlib.util\nimport io\nimport json\nimport shutil\nimport sys\nimport tempfile\nimport unittest\nimport urllib.error\nfrom pathlib import Path\nfrom unittest import mock\n''',
)
replace_once(
    "automation/tests/test_image_preview.py",
    '''    def test_invalid_base64_is_rejected(self) -> None:\n        def invalid_transport(**kwargs):\n            return {"data": [{"b64_json": "***not-base64***"}]}\n\n        with self.assertRaisesRegex(generator.ImageGenerationError, "base64"):\n            generator.generate_image_artifact(\n                source_dir=self.source,\n                output_dir=self.output,\n                request_path=self.request_path,\n                config_path=CONFIG,\n                api_key="test-key-not-sent",\n                model="gpt-image-2",\n                transport=invalid_transport,\n            )\n''',
    '''    def test_invalid_base64_is_rejected(self) -> None:\n        def invalid_transport(**kwargs):\n            return {"data": [{"b64_json": "***not-base64***"}]}\n\n        with self.assertRaisesRegex(generator.ImageApiResponseError, "base64"):\n            generator.generate_image_artifact(\n                source_dir=self.source,\n                output_dir=self.output,\n                request_path=self.request_path,\n                config_path=CONFIG,\n                api_key="test-key-not-sent",\n                model="gpt-image-2",\n                transport=invalid_transport,\n            )\n\n    def test_missing_editorial_request_id_does_not_block_image_call(self) -> None:\n        for name in ("image-source.json", "run-info.json", "digest.json"):\n            path = self.source / name\n            if not path.exists():\n                continue\n            payload = json.loads(path.read_text(encoding="utf-8"))\n            payload.pop("request_id", None)\n            payload.pop("editorial_request_id", None)\n            path.write_text(\n                json.dumps(payload, ensure_ascii=False, indent=2) + "\\n",\n                encoding="utf-8",\n            )\n\n        result = generator.generate_image_artifact(\n            source_dir=self.source,\n            output_dir=self.output,\n            request_path=self.request_path,\n            config_path=CONFIG,\n            api_key="test-key-not-sent",\n            model="gpt-image-2",\n            transport=self.fake_transport,\n        )\n        self.assertEqual(result["status"], "ok")\n        self.assertIsNotNone(self.captured_request)\n        metadata = json.loads(\n            (self.output / "image-request.json").read_text(encoding="utf-8")\n        )\n        self.assertEqual(metadata["image_request_id"], "image-preview-test-001")\n        self.assertIsNone(metadata["source_editorial_request_id"])\n\n    def test_missing_image_request_id_still_fails_before_transport(self) -> None:\n        payload = json.loads(self.request_path.read_text(encoding="utf-8"))\n        payload["request_id"] = ""\n        self.request_path.write_text(\n            json.dumps(payload, ensure_ascii=False, indent=2) + "\\n",\n            encoding="utf-8",\n        )\n        with self.assertRaisesRegex(generator.ImagePreflightError, "request_id"):\n            generator.generate_image_artifact(\n                source_dir=self.source,\n                output_dir=self.output,\n                request_path=self.request_path,\n                config_path=CONFIG,\n                api_key="test-key-not-sent",\n                model="gpt-image-2",\n                transport=self.fake_transport,\n            )\n        self.assertIsNone(self.captured_request)\n\n    def test_http_error_preserves_openai_request_id_and_error_code(self) -> None:\n        body = json.dumps(\n            {\n                "error": {\n                    "message": "quota exhausted",\n                    "type": "insufficient_quota",\n                    "code": "insufficient_quota",\n                }\n            }\n        ).encode("utf-8")\n        http_error = urllib.error.HTTPError(\n            "https://api.openai.com/v1/images/generations",\n            429,\n            "Too Many Requests",\n            {"x-request-id": "req_image_123"},\n            io.BytesIO(body),\n        )\n        with mock.patch.object(\n            generator.urllib.request, "urlopen", side_effect=http_error\n        ):\n            with self.assertRaises(generator.ImageApiHttpError) as caught:\n                generator.default_transport(\n                    api_url="https://api.openai.com/v1/images/generations",\n                    api_key="test-key-not-sent",\n                    request_payload={"model": "gpt-image-2", "prompt": "test"},\n                    timeout_seconds=10,\n                )\n        self.assertEqual(caught.exception.http_status, 429)\n        self.assertEqual(caught.exception.openai_request_id, "req_image_123")\n        self.assertEqual(caught.exception.api_error_code, "insufficient_quota")\n''',
)

workflow_test = '''from __future__ import annotations\n\nimport unittest\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[2]\nWORKFLOW = ROOT / ".github" / "workflows" / "daily-production.yml"\n\n\nclass ImageStageRecoveryContractTests(unittest.TestCase):\n    def test_validated_digest_is_checkpointed_before_cover_generation(self) -> None:\n        text = WORKFLOW.read_text(encoding="utf-8")\n        story = text.index("- name: Validate publishable story count and short digest marker")\n        request = text.index("- name: Build runtime Image API request")\n        cover = text.index("- name: Generate one production cover")\n        self.assertLess(story, request)\n        self.assertLess(request, cover)\n\n    def test_late_cover_failure_keeps_a_reusable_rank_two_artifact(self) -> None:\n        text = WORKFLOW.read_text(encoding="utf-8")\n        self.assertIn(\n            'elif any($steps[]; (.name == "Validate publishable story count and short digest marker" and .conclusion == "success")) then 2',\n            text,\n        )\n        self.assertIn("uses: actions/upload-artifact@v7", text)\n        upload = text.index("uses: actions/upload-artifact@v7")\n        self.assertIn("if: always()", text[max(0, upload - 160):upload])\n\n    def test_recovered_cover_skips_another_image_call(self) -> None:\n        text = WORKFLOW.read_text(encoding="utf-8")\n        self.assertIn("steps.recovery.outputs.image_recovered != 'true'", text)\n        self.assertIn("- name: Revalidate recovered production cover", text)\n\n\nif __name__ == "__main__":\n    unittest.main()\n'''
workflow_test_path = ROOT / "automation/tests/test_image_stage_recovery_contract.py"
workflow_test_path.write_text(workflow_test, encoding="utf-8")

# 3. Keep documentation synchronized with the actual paid-stage recovery contract.
replace_once(
    "automation/README.md",
    "2. `major_agencies` — Reuters, AP, Bloomberg, FT;",
    "2. `major_agencies` — дополнительный high-signal route по Bloomberg и FT;",
)

append_once(
    "AGENTS.md",
    "## Paid-stage recovery and image provenance",
    '''## Paid-stage recovery and image provenance\n\nA validated digest is a paid-stage checkpoint. Once `Validate publishable story\ncount and short digest marker` has succeeded for a publication date, a later\ncover/build/commit/deploy failure must not cause Primary, Hybrid, Coverage or\neditorial to be repaid automatically. Recovery must reuse the highest-completeness\nnon-expired artifact and resume from the first incomplete stage. A successfully\nvalidated cover is a still later checkpoint; FTP-only failure must reuse the\ncommitted release instead of regenerating research or the cover.\n\nImage provenance uses separate identities. `image_request_id` is mandatory for\nthe image operation. `source_editorial_request_id` is optional provenance and\nmust never block an otherwise valid recovered digest from reaching the Images\nAPI. Never fabricate an editorial ID from an image ID. A real Images API call\nshould preserve the provider `x-request-id` when available. Image failures must\nbe classified as local preflight, transport/HTTP, or response/contract failures\nso operators can distinguish a zero-cost metadata failure from a billable API\nattempt. Automatic image retries remain disabled; one production cover means at\nmost one Images API call unless an operator explicitly starts a new recovery run.''',
)

append_once(
    "README.md",
    "## Возобновляемые платные стадии",
    '''## Возобновляемые платные стадии\n\nProduction рассматривает успешно провалидированный текст выпуска как отдельный\ncheckpoint. Если после него ломается обложка, сборка сайта, commit или FTP,\nследующий recovery-run переиспользует готовый artifact и не оплачивает заново\nPrimary Recall, Hybrid, Coverage и редактуру. Успешная обложка является следующим\ncheckpoint, а уже закоммиченный выпуск при проблеме FTP только redeploy-ится.\n\nДля обложки обязательным идентификатором является отдельный `image_request_id`.\nИсходный `source_editorial_request_id` хранится только как provenance и может\nотсутствовать у корректного recovery-артефакта; его отсутствие не должно\nостанавливать Image API. Диагностика различает локальный image-preflight,\nсетевой/HTTP сбой Images API и некорректный API response, а при доступности\nсохраняет `x-request-id`. Обычная генерация обложки остаётся one-shot без\nавтоматического retry.''',
)

append_once(
    "automation/README.md",
    "## Recovery платных стадий и обложки",
    '''## Recovery платных стадий и обложки\n\nУспешный `Validate publishable story count and short digest marker` фиксирует\nтекстовый paid checkpoint. Ошибка на обложке или любом более позднем шаге не\nразрешает автоматически повторять Primary/Hybrid/Coverage/editorial: следующий\nrun должен выбрать сохранённый artifact completeness rank 2 и продолжить с\nImage API. После валидной обложки recovery использует image-complete artifact и\nтоже не вызывает Images API заново. Artifact upload выполняется `if: always()`,\nпоэтому поздняя красная стадия не уничтожает уже оплаченный результат.\n\n`generate_image_preview.py` разделяет идентификаторы: обязательный\n`image_request_id`, опциональный `source_editorial_request_id` и provider\n`openai_request_id` (`x-request-id`, если он есть). Отсутствующий editorial ID у\nrecovery-артефакта является допустимым provenance gap, а не image-preflight\nошибкой. Настоящие сбои классифицируются как `image_preflight`,\n`image_api_transport`, `image_api_http` или `image_api_response`. Один запуск\nобложки делает максимум один Images API POST и не имеет внутреннего retry-loop.''',
)

print("cover fix applied")
