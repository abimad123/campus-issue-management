from django.test import SimpleTestCase
class HealthViewTests(SimpleTestCase):
    def test_health_endpoint_reports_running_service(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["service"], "LPU Campus API")
