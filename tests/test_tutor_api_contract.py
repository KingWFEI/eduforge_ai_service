import unittest

from app.main import app


class TutorApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.openapi_schema = None
        cls.schema = app.openapi()

    def test_tutor_endpoints_use_ai_assistant_qa_tag(self):
        tutor_paths = {
            path: methods
            for path, methods in self.schema["paths"].items()
            if path.startswith("/api/tutor")
        }
        self.assertEqual(len(tutor_paths), 5)
        for methods in tutor_paths.values():
            for method, operation in methods.items():
                if method.upper() in {"GET", "POST"}:
                    self.assertEqual(operation["tags"], ["AI辅助问答"])

    def test_json_endpoints_use_standard_response_envelope(self):
        operations = [
            ("/api/tutor/sessions/enter", "post"),
            ("/api/tutor/sessions", "get"),
            ("/api/tutor/sessions/{session_id}/messages", "get"),
            ("/api/tutor/sessions/{session_id}/close", "post"),
        ]
        for path, method in operations:
            operation = self.schema["paths"][path][method]
            response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
            component_name = response_schema["$ref"].rsplit("/", 1)[-1]
            properties = self.schema["components"]["schemas"][component_name]["properties"]
            self.assertEqual(set(properties), {"code", "message", "data"})

    def test_tutor_validation_docs_match_global_error_envelope(self):
        for path, methods in self.schema["paths"].items():
            if not path.startswith("/api/tutor"):
                continue
            for method, operation in methods.items():
                if method.upper() not in {"GET", "POST"}:
                    continue
                self.assertNotIn("422", operation["responses"])
                error_schema = operation["responses"]["400"]["content"]["application/json"]["schema"]
                self.assertEqual(
                    set(error_schema["properties"]),
                    {"code", "message", "data"},
                )

    def test_stream_endpoint_documents_standard_sse_event_envelope(self):
        operation = self.schema["paths"]["/api/tutor/sessions/{session_id}/stream"]["post"]
        stream_content = operation["responses"]["200"]["content"]["text/event-stream"]
        example = stream_content["example"]
        self.assertIn("event: delta", example)
        self.assertIn('"code": 0', example)
        self.assertIn('"message": "success"', example)
        self.assertIn('"data":', example)


if __name__ == "__main__":
    unittest.main()
