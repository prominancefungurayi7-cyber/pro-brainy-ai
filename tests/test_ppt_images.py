import json
import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from services.ppt_image_service import _allowed_media_url, find_diagram


class CommonsDiagramTests(unittest.TestCase):
    def test_media_url_rejects_external_hosts_and_redirect_paths(self):
        self.assertTrue(_allowed_media_url(
            'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/example.png'
        ))
        self.assertTrue(_allowed_media_url(
            'https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/example.png'
        ))
        for url in (
            'http://upload.wikimedia.org/wikipedia/commons/x.png',
            'https://upload.wikimedia.org.evil.test/wikipedia/commons/x.png',
            'https://upload.wikimedia.org/wikipedia/commons/../private/x.png',
            'https://upload.wikimedia.org/wikipedia/commons/x.png?token=secret',
        ):
            with self.subTest(url=url):
                self.assertFalse(_allowed_media_url(url))

    @patch('services.ppt_image_service._fetch_bounded')
    def test_fetches_licensed_relevant_image_and_preserves_attribution(self, fetch):
        image = BytesIO()
        Image.new('RGB', (80, 40), 'green').save(image, format='PNG')
        metadata = {
            'query': {'pages': [{
                'index': 0, 'title': 'File:Water cycle diagram.png',
                'imageinfo': [{
                    'thumburl': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/water.png?utm_source=commons.wikimedia.org',
                    'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Water_cycle_diagram.png',
                    'extmetadata': {
                        'Artist': {'value': '<a>Example Artist</a>'},
                        'LicenseShortName': {'value': 'CC BY 4.0'},
                        'LicenseUrl': {'value': 'https://creativecommons.org/licenses/by/4.0/'},
                    },
                }],
            }]},
        }
        fetch.side_effect = [
            (json.dumps(metadata).encode(), 'application/json'),
            (image.getvalue(), 'image/png'),
        ]
        result = find_diagram('water cycle')
        self.assertIsNotNone(result)
        self.assertEqual(result.attribution, 'Example Artist')
        self.assertEqual(result.license, 'CC BY 4.0')
        self.assertEqual(result.image_bytes, image.getvalue())
        self.assertEqual(
            fetch.call_args_list[1].args[0],
            'https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/water.png',
        )

    @patch('services.ppt_image_service._fetch_bounded')
    def test_unlicensed_results_never_download(self, fetch):
        metadata = {
            'query': {'pages': [{
                'index': 0, 'title': 'File:Water cycle diagram.png',
                'imageinfo': [{
                    'thumburl': 'https://upload.wikimedia.org/wikipedia/commons/x.png',
                    'extmetadata': {
                        'Artist': {'value': 'Artist'},
                        'LicenseShortName': {'value': 'Unknown'},
                    },
                }],
            }]},
        }
        fetch.return_value = json.dumps(metadata).encode(), 'application/json'
        self.assertIsNone(find_diagram('water cycle'))
        self.assertEqual(fetch.call_count, 1)


if __name__ == '__main__':
    unittest.main()
