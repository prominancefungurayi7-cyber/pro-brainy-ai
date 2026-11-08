import json
import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from pptx import Presentation

from app import app
from models.user import db
from services.ppt_image_service import DiagramImage
from tests.helpers import csrf_token, register_client


def plan(slides=2):
    return json.dumps({'slides': [
        {
            'title': f'Water cycle stage {index + 1}',
            'key_message': 'Water changes location and form.',
            'bullets': ['Evaporation moves water into the air.',
                        'Condensation forms clouds from water vapour.'],
            'explanation': 'Explain how energy and temperature affect this stage.',
            'diagram_query': 'water cycle diagram',
        }
        for index in range(slides)
    ]})


class PowerPointDownloadTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
        register_client(self.client)

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    @patch('services.ppt_service.find_diagram', return_value=None)
    @patch('services.ppt_service.generate_response', return_value=plan())
    def test_download_is_real_pptx_with_notes_and_detail_selection(self, generate, find):
        for detail in ('fully_explanatory', 'medium', 'straightforward'):
            with self.subTest(detail=detail):
                response = self.client.post('/ppt/download', data={
                    '_csrf_token': csrf_token(self.client),
                    'topic': 'The water cycle', 'audience': 'Secondary students',
                    'slides': '3', 'detail_level': detail,
                    'include_diagrams': 'on',
                })
                self.assertEqual(response.status_code, 200)
                self.assertIn('presentationml.presentation', response.content_type)
                self.assertIn('.pptx', response.headers['Content-Disposition'])
                deck = Presentation(BytesIO(response.data))
                self.assertEqual(len(deck.slides), 3)
                self.assertIn('The water cycle', ' '.join(
                    shape.text for shape in deck.slides[0].shapes if shape.has_text_frame
                ))
                self.assertIn('Evaporation', ' '.join(
                    shape.text for shape in deck.slides[1].shapes if shape.has_text_frame
                ))
                self.assertIn('Explain how energy', deck.slides[1].notes_slide.notes_text_frame.text)
                self.assertIn(detail, generate.call_args.args[0])
        self.assertTrue(find.called)

    @patch('services.ppt_service.find_diagram')
    @patch('services.ppt_service.generate_response', return_value=plan())
    def test_licensed_diagram_is_embedded_with_credit(self, _generate, find):
        image = BytesIO()
        Image.new('RGB', (240, 120), 'blue').save(image, format='PNG')
        find.return_value = DiagramImage(
            image_bytes=image.getvalue(), title='Water cycle diagram',
            attribution='Example Author', license='CC BY 4.0',
            license_url='https://creativecommons.org/licenses/by/4.0/',
            source_url='https://commons.wikimedia.org/wiki/File:Water_cycle.png',
        )
        response = self.client.post('/ppt/download', data={
            '_csrf_token': csrf_token(self.client),
            'topic': 'The water cycle', 'slides': '3',
            'detail_level': 'medium', 'include_diagrams': 'on',
        })
        self.assertEqual(response.status_code, 200)
        deck = Presentation(BytesIO(response.data))
        self.assertTrue(any(shape.shape_type == 13 for shape in deck.slides[1].shapes))
        notes = deck.slides[1].notes_slide.notes_text_frame.text
        self.assertIn('Example Author', notes)
        self.assertIn('creativecommons.org/licenses/by/4.0/', notes)
        self.assertIn('commons.wikimedia.org/wiki/File:', notes)

    @patch('services.ppt_service.find_diagram')
    @patch('services.ppt_service.generate_response', return_value=plan())
    def test_specific_search_falls_back_to_topic_once(self, _generate, find):
        image = BytesIO()
        Image.new('RGB', (240, 120), 'blue').save(image, format='PNG')
        diagram = DiagramImage(
            image_bytes=image.getvalue(), title='Water cycle diagram',
            attribution='Example Author', license='CC BY 4.0',
            license_url='https://creativecommons.org/licenses/by/4.0/',
            source_url='https://commons.wikimedia.org/wiki/File:Water_cycle.png',
        )
        find.side_effect = lambda query: diagram if query == 'The water cycle' else None
        response = self.client.post('/ppt/download', data={
            '_csrf_token': csrf_token(self.client),
            'topic': 'The water cycle', 'slides': '3',
            'detail_level': 'medium', 'include_diagrams': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([call.args[0] for call in find.call_args_list],
                         ['water cycle diagram', 'The water cycle', 'water cycle diagram'])
        deck = Presentation(BytesIO(response.data))
        self.assertTrue(any(shape.shape_type == 13 for shape in deck.slides[1].shapes))

    @patch('services.ppt_service.find_diagram', side_effect=OSError('external media unavailable'))
    @patch('services.ppt_service.generate_response', return_value=plan())
    def test_diagram_network_failure_does_not_break_download(self, _generate, _find):
        response = self.client.post('/ppt/download', data={
            '_csrf_token': csrf_token(self.client),
            'topic': 'The water cycle', 'slides': '3',
            'detail_level': 'medium', 'include_diagrams': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(Presentation(BytesIO(response.data)).slides), 3)

    @patch('services.ppt_service.generate_response')
    def test_invalid_slide_count_does_not_call_ai(self, generate):
        response = self.client.post('/ppt/download', data={
            '_csrf_token': csrf_token(self.client),
            'topic': 'Water cycle', 'slides': '30', 'detail_level': 'medium',
        }, headers={'Accept': 'application/json'})
        self.assertEqual(response.status_code, 422)
        self.assertIn(b'3 to 12', response.data)
        generate.assert_not_called()

    @patch('services.ppt_service.generate_response', return_value='{"slides": []}')
    def test_incomplete_ai_plan_returns_clear_error(self, _generate):
        response = self.client.post('/ppt/download', data={
            '_csrf_token': csrf_token(self.client),
            'topic': 'Water cycle', 'slides': '3', 'detail_level': 'medium',
        }, headers={'Accept': 'application/json'})
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'plan was incomplete', response.data)

    @patch('services.ppt_service.find_diagram')
    @patch('services.ppt_service.generate_response', return_value=plan(11))
    def test_maximum_supported_deck_stays_within_slide_canvas(self, _generate, find):
        response = self.client.post('/ppt/download', data={
            '_csrf_token': csrf_token(self.client),
            'topic': 'The water cycle', 'slides': '12',
            'detail_level': 'fully_explanatory',
        })
        self.assertEqual(response.status_code, 200)
        deck = Presentation(BytesIO(response.data))
        self.assertEqual(len(deck.slides), 12)
        for slide in deck.slides:
            for shape in slide.shapes:
                self.assertGreaterEqual(shape.left, 0)
                self.assertGreaterEqual(shape.top, 0)
                self.assertLessEqual(shape.left + shape.width, deck.slide_width)
                self.assertLessEqual(shape.top + shape.height, deck.slide_height)
        find.assert_not_called()


if __name__ == '__main__':
    unittest.main()
