import unittest
import struct
import xml.etree.ElementTree as ET

from edk2toolext.perf.fpdt_parser import (
    AcpiTableHeader,
)


class TestAcpiTableHeader(unittest.TestCase):
    def setUp(self):
        # Prepare a valid binary header with known values
        self.sample_data = struct.pack(
            "=4sIBB6s8sI4sI",
            b"TEST",  # Signature
            0x12345678,  # Length
            0x01,  # Revision
            0x5A,  # Checksum
            b"OEM123",  # OEM ID
            b"TBLID456",  # OEM Table ID
            0x87654321,  # OEM Revision
            b"CRID",  # Creator ID
            0xABCDEF01,  # Creator Revision
        )
        self.header = AcpiTableHeader(self.sample_data)

    def test_fields_parsed_correctly(self):
        self.assertEqual(self.header.signature, "TEST")
        self.assertEqual(self.header.length, 0x12345678)
        self.assertEqual(self.header.revision, 0x01)
        self.assertEqual(self.header.checksum, 0x5A)
        self.assertEqual(self.header.oem_id, b"OEM123")
        self.assertEqual(self.header.oem_table_id, b"TBLID456")
        self.assertEqual(self.header.oem_revision, 0x87654321)
        self.assertEqual(self.header.creator_id, b"CRID")
        self.assertEqual(self.header.creator_revision, 0xABCDEF01)

    def test_str_representation(self):
        output = str(self.header)
        self.assertIn("Signature        : TEST", output)
        self.assertIn("Length           : 0x12345678", output)
        self.assertIn("OEM ID           : b'OEM123'", output)

    def test_to_xml(self):
        xml = self.header.to_xml()
        self.assertIsInstance(xml, ET.Element)
        self.assertEqual(xml.get("Signature"), "TEST")
        self.assertEqual(xml.get("Length"), "0x12345678")
        self.assertEqual(xml.get("OEMID"), "b'OEM123'")
        self.assertEqual(xml.get("CreatorRevision"), "0xABCDEF01")


if __name__ == "__main__":
    unittest.main()
