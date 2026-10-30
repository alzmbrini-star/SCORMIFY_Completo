import unittest
from services.component_catalog import catalog, COMPONENTS, SEARCH_TERMS


class ComponentFilterMetadataTests(unittest.TestCase):
    def test_catalog_adds_detached_search_metadata_only(self):
        result = catalog()
        self.assertEqual(set(result['components']), set(COMPONENTS))
        for key, definition in result['components'].items():
            self.assertTrue(definition['searchTerms'])
            self.assertTrue(all(isinstance(term, str) for term in definition['searchTerms']))
            self.assertEqual({k: v for k, v in definition.items() if k != 'searchTerms'}, COMPONENTS[key])
        result['components']['liquid_vessel']['searchTerms'].append('changed')
        self.assertNotIn('changed', SEARCH_TERMS['liquid_vessel'])
        self.assertNotIn('searchTerms', COMPONENTS['liquid_vessel'])


if __name__ == '__main__':
    unittest.main()
