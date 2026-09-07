import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.agents import _meeting_route, meeting_agent, supervisor
from src.graph import _session_meeting, ask
from src.multimodal import (
    _clean_scalar,
    _consistent_dates,
    _empty_context,
    _plain_text,
    _supplement_audio_facts,
)
from src.tools import update_initiative_from_meeting


class GraphTests(unittest.TestCase):
    def test_existing_technical_query(self):
        response = ask("¿Cuál es el avance técnico de Samsung Pay?", show_trace=False)
        self.assertIn("75 %", response)
        self.assertIn("Technical Status Agent", response)

    def test_existing_procedure_query(self):
        response = ask("¿Cómo hago un pase a producción?", show_trace=False)
        self.assertIn("PROCEDIMIENTO: Pase a producción", response)

    def test_meeting_path_is_extracted(self):
        state = {"user_query": 'Procesa la reunión "input/mi reunion.mp4"'}
        result = _meeting_route(state)
        self.assertEqual("input/mi reunion.mp4", result["meeting_file"])
        self.assertEqual(["meeting"], result["required_agents"])

    def test_mov_path_is_extracted(self):
        state = {"user_query": 'Procesa la reunión "input/mi reunion.mov"'}
        result = _meeting_route(state)
        self.assertEqual("input/mi reunion.mov", result["meeting_file"])
        self.assertEqual(["meeting"], result["required_agents"])

    def test_meeting_question_routes_without_context(self):
        result = supervisor({"user_query": "¿Qué se acordó en la reunión?"})
        self.assertEqual("reunion_multimodal", result["intent"])

    @patch("src.agents.load_json")
    @patch("src.agents.get_initiative", return_value=None)
    def test_saved_video_can_be_queried_after_restart(self, get_initiative, load_json):
        context = {"initiative": "Samsung Pay Visa", "progress_percentage": 90}
        load_json.return_value = [
            {"name": "Samsung Pay Visa", "last_meeting_update": context}
        ]
        result = meeting_agent({
            "user_query": "¿Qué datos se encontraron en el video?",
            "required_agents": ["meeting"],
        })
        self.assertEqual(context, result["meeting_context"])

    def test_latest_meeting_combines_existing_agents(self):
        result = supervisor({"user_query": "¿Cómo va Samsung Pay considerando la última reunión?"})
        self.assertEqual(["initiative", "tracking", "technical", "meeting"], result["required_agents"])

    def test_explicit_command_routes_to_persistent_update(self):
        state = {
            "user_query": "Actualiza la iniciativa con lo del video",
            "meeting_context": {"initiative": "Samsung Pay Visa", "agreements": ["Acuerdo"]},
        }
        result = supervisor(state)
        self.assertEqual("actualizar_desde_reunion", result["intent"])
        self.assertEqual("Samsung Pay Visa", result["initiative_name"])
        self.assertEqual(["update"], result["required_agents"])

    def test_explicit_update_writes_separate_meeting_block(self):
        initiatives = [{"name": "Samsung Pay Visa", "status": "UAT"}]
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "initiatives.json").write_text(
                json.dumps(initiatives), encoding="utf-8"
            )
            context = {
                "initiative": "Samsung Pay Visa", "pending": ["Security Scan"],
                "status": "Listo para producción", "target_date": "2026-08-28",
                "progress_percentage": "90%",
            }
            with patch("src.tools.DATA_DIR", data_dir):
                message = update_initiative_from_meeting("Samsung Pay Visa", context)
            saved = json.loads((data_dir / "initiatives.json").read_text(encoding="utf-8"))[0]

        self.assertIn("actualizada", message)
        self.assertEqual("Listo para producción", saved["status"])
        self.assertEqual("2026-08-28", saved["target_date"])
        self.assertEqual(90.0, saved["progress_percentage"])
        self.assertEqual(["Security Scan"], saved["meeting_pending"])
        self.assertEqual(context, saved["last_meeting_update"])

    def test_audio_fallback_extracts_real_meeting_values(self):
        transcription = (
            "El avance está al 90%. Básicamente no es el 75%. "
            "La fecha estimada es para el 5 de septiembre del 2026. Es una prioridad alta."
        )
        facts = _supplement_audio_facts(transcription, _empty_context())
        self.assertEqual(90, facts["progress_percentage"])
        self.assertEqual("2026-09-05", facts["target_date"])
        self.assertEqual("Alta", facts["priority"])
        self.assertIsNone(facts["status"])

    def test_nested_visual_value_is_cleaned(self):
        self.assertEqual("28 de agosto de 2026", _plain_text({"text": "28 de agosto de 2026"}))
        self.assertIsNone(_clean_scalar("null"))
        self.assertEqual(
            ["5 de septiembre de 2026"],
            _consistent_dates(
                ["5 de septiembre de 2026", "2020-08-28"], "2026-09-05"
            ),
        )

    @patch("src.multimodal.process_meeting")
    def test_meeting_context_survives_during_session(self, process_meeting):
        context = {
            "initiative": "Samsung Pay Visa",
            "dates": ["28 de agosto"],
            "responsibles": ["Carlos gestionará el CAB"],
            "agreements": ["Salir a producción el 28 de agosto"],
            "pending": ["Security Scan: PENDING"],
            "risks": [],
            "technical_information": ["Pipeline: SUCCESS"],
            "sources": {
                "audio de la reunión": {
                    "dates": ["28 de agosto"], "responsibles": ["Carlos gestionará el CAB"],
                    "agreements": ["Salir a producción el 28 de agosto"], "pending": [],
                    "risks": [], "technical_information": [],
                },
                "pantalla compartida": {
                    "dates": [], "responsibles": [], "agreements": [],
                    "pending": ["Security Scan: PENDING"], "risks": [],
                    "technical_information": ["Pipeline: SUCCESS"],
                },
            },
        }
        process_meeting.return_value = ("Transcripción de prueba", [], context)
        _session_meeting.clear()

        ask("Procesa la reunión input/reunion_samsung_pay.mp4", show_trace=False)
        response = ask("¿El Security Scan está terminado?", show_trace=False)

        self.assertIn("Security Scan: PENDING", response)
        self.assertIn("Pantalla compartida", response)


if __name__ == "__main__":
    unittest.main()
