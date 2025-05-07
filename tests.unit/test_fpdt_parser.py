from ctypes import c_ulong, c_void_p, create_string_buffer
import datetime
import os
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import edk2toolext
import pytest
from unittest.mock import Mock, patch, call, MagicMock
from unittest import mock
import sys
import types
import glob


from edk2toolext.perf.fpdt_parser import (
    FPDT_PARSER_VER,
    AcpiTableHeader,
    FwBasicBootPerformanceRecord,
    FwBasicBootPerformanceTableHeader,
    FbptRecordHeader,
    FwBasicBootPerformanceDataRecord,
    GuidEventRecord,
    DynamicStringEventRecord,
    DualGuidStringEventRecord,
    GuidQwordEventRecord,
    GuidQwordStringEventRecord,
    FIRMWARE_BASIC_BOOT_PERFORMANCE_DATA_EVENT_TYPE,
    GUID_EVENT_TYPE,
    DYNAMIC_STRING_EVENT_TYPE,
    FPDT_DYNAMIC_STRING_EVENT_TYPE,
    DUAL_GUID_STRING_EVENT_TYPE,
    FPDT_DUAL_GUID_STRING_EVENT_TYPE,
    GUID_QWORD_EVENT_TYPE,
    FPDT_GUID_QWORD_EVENT_TYPE,
    GUID_QWORD_STRING_EVENT_TYPE,
    FPDT_GUID_QWORD_STRING_EVENT_TYPE,
    ParserApp,
    SystemFirmwareTable,
    fbpt_parsing_factory,
    get_model,
    get_uefi_version,
)


class TestAcpiTableHeader:
    @pytest.fixture
    def header_bytes(self):
        return struct.pack(
            AcpiTableHeader.struct_format,
            b"TEST",
            44,
            2,
            255,
            b"OEMID1",
            b"TABLE123",
            12345678,
            b"CRID",
            87654321,
        )

    def test_init(self, header_bytes):
        header = AcpiTableHeader(header_bytes)
        assert header.signature == "TEST"
        assert header.length == 44
        assert header.revision == 2
        assert header.checksum == 255
        assert header.oem_id == b"OEMID1"
        assert header.oem_table_id == b"TABLE123"
        assert header.oem_revision == 12345678
        assert header.creator_id == b"CRID"
        assert header.creator_revision == 87654321

    def test_str(self, header_bytes):
        header = AcpiTableHeader(header_bytes)
        s = str(header)
        assert "Signature        : TEST" in s
        assert "OEM ID           : b'OEMID1'" in s

    def test_to_xml(self, header_bytes):
        header = AcpiTableHeader(header_bytes)
        xml = header.to_xml()
        assert xml.tag == "AcpiTableHeader"
        assert xml.get("Signature") == "TEST"
        assert xml.get("Length") == "0x2C"


class TestFwBasicBootPerformanceRecord:
    @pytest.fixture
    def record_bytes(self):
        return struct.pack(
            FwBasicBootPerformanceRecord.struct_format, 1, 24, 1, 0, 0xABCDEF1234567890
        )

    def test_init(self, record_bytes):
        rec = FwBasicBootPerformanceRecord(record_bytes)
        assert rec.performance_record_type == 1
        assert rec.record_length == 24
        assert rec.revision == 1
        assert rec.reserved == 0
        assert rec.fbpt_pointer == 0xABCDEF1234567890

    def test_str(self, record_bytes):
        rec = FwBasicBootPerformanceRecord(record_bytes)
        out = str(rec)
        assert "FBPT Pointer" in out
        assert "0xABCDEF1234567890" in out

    def test_to_xml(self, record_bytes):
        rec = FwBasicBootPerformanceRecord(record_bytes)
        xml = rec.to_xml()
        assert xml.tag == "FwBasicBootPerformanceRecord"
        assert xml.get("FBPTPointer") == "0xABCDEF1234567890"


class TestFwBasicBootPerformanceTableHeader:
    @pytest.fixture
    def table_bytes(self):
        return struct.pack(FwBasicBootPerformanceTableHeader.struct_format, b"FBPT", 64)

    def test_init(self, table_bytes):
        header = FwBasicBootPerformanceTableHeader(table_bytes)
        assert header.signature == "FBPT"
        assert header.length == 64

    def test_str(self, table_bytes):
        header = FwBasicBootPerformanceTableHeader(table_bytes)
        s = str(header)
        assert "FBPT" in s
        assert "0x00000040" in s

    def test_to_xml(self, table_bytes):
        header = FwBasicBootPerformanceTableHeader(table_bytes)
        xml = header.to_xml()
        assert xml.tag == "Fbpt"
        assert xml.get("Length") == "0x40"


# ---------------------------------------
# FBPT RECORD HEADER
# ---------------------------------------


class TestFbptRecordHeader:
    @pytest.mark.parametrize(
        "record_type,expected_tag",
        [
            (
                FIRMWARE_BASIC_BOOT_PERFORMANCE_DATA_EVENT_TYPE,
                "FirmwareBasicBootPerformanceEvent",
            ),
            (GUID_EVENT_TYPE, "GuidEvent"),
            (DYNAMIC_STRING_EVENT_TYPE, "DynamicStringEvent"),
            (FPDT_DYNAMIC_STRING_EVENT_TYPE, "DynamicStringEvent"),
            (DUAL_GUID_STRING_EVENT_TYPE, "DualGuidStringEvent"),
            (FPDT_DUAL_GUID_STRING_EVENT_TYPE, "DualGuidStringEvent"),
            (GUID_QWORD_EVENT_TYPE, "GuidQwordEvent"),
            (FPDT_GUID_QWORD_EVENT_TYPE, "GuidQwordEvent"),
            (GUID_QWORD_STRING_EVENT_TYPE, "GuidQwordStringEvent"),
            (FPDT_GUID_QWORD_STRING_EVENT_TYPE, "GuidQwordStringEvent"),
            (0xFFFF, "UnknownEvent"),
        ],
    )
    def test_to_xml_known(self, record_type, expected_tag):
        packed = struct.pack(FbptRecordHeader.struct_format, record_type, 0x20, 0x01)
        header = FbptRecordHeader(packed)
        xml = header.to_xml()
        assert xml.tag == expected_tag
        assert xml.get("PerformanceRecordType") == f"0x{record_type:X}"
        assert xml.get("RecordLength") == "0x20"
        assert xml.get("Revision") == "0x1"

    def test_str(self):
        packed = struct.pack(FbptRecordHeader.struct_format, 0x1234, 0x20, 0x01)
        header = FbptRecordHeader(packed)
        output = str(header)
        assert "0x1234" in output
        assert "0x20" in output
        assert "0x01" in output


class MockFbptRecordHeader:
    def to_xml(self):
        return ET.Element("MockHeader")

    def __str__(self):
        return "MockHeader"


@pytest.fixture
def mock_header():
    return MockFbptRecordHeader()


class TestFwBasicBootPerformanceDataRecord:
    @pytest.fixture
    def sample_bytes(self):
        return struct.pack(
            FwBasicBootPerformanceDataRecord.struct_format,
            0xABCD1234,
            1000000,
            2000000,
            3000000,
            4000000,
            5000000,
        )

    def test_init_fields(self, mock_header, sample_bytes):
        record = FwBasicBootPerformanceDataRecord(mock_header, sample_bytes)

        assert record.reserved == 0xABCD1234
        assert record.reset_end == 1000000
        assert record.os_loader_load_image_start == 2000000
        assert record.os_loader_start_image_start == 3000000
        assert record.exit_boot_services_entry == 4000000
        assert record.exit_boot_services_exit == 5000000

    def test_str(self, mock_header, sample_bytes):
        record = FwBasicBootPerformanceDataRecord(mock_header, sample_bytes)
        result = str(record)
        assert "Reserved" in result
        assert "0xABCD1234" in result
        assert "Reset End" in result
        assert "0x00000000000F4240" in result  # 1000000 in hex

    def test_to_xml(self, mock_header, sample_bytes):
        record = FwBasicBootPerformanceDataRecord(mock_header, sample_bytes)
        xml_elem = record.to_xml()

        assert xml_elem.find("ResetEnd").get("RawValue") == "0xF4240"
        assert xml_elem.find("ResetEnd").get("ValueInMilliseconds") == "1.000000"

        assert xml_elem.find("OSLoaderLoadImageStart").get("RawValue") == "0x1E8480"
        assert (
            xml_elem.find("OSLoaderLoadImageStart").get("ValueInMilliseconds")
            == "2.000000"
        )

        assert xml_elem.find("OSLoaderStartImageStart").get("RawValue") == "0x2DC6C0"
        assert xml_elem.find("ExitBootServicesEntry").get("RawValue") == "0x3D0900"
        assert xml_elem.find("ExitBootServicesExit").get("RawValue") == "0x4C4B40"


class TestGuidEventRecord:
    @pytest.fixture
    def sample_data(self):
        # Packing data for the GuidEventRecord struct
        contents = struct.pack(
            "=HIQIHHBBBBBBBB",
            0x1234,  # progress_id
            0x56789ABC,  # apic_id
            0xABCDEF0123456789,  # timestamp
            0xDEADBEEF,  # guid_uint32
            0xBEEF,  # guid_uint16_0
            0xFEED,  # guid_uint16_1
            0xDE,  # guid_uint8_0
            0xAD,  # guid_uint8_1
            0xBE,  # guid_uint8_2
            0xEF,  # guid_uint8_3
            0x01,  # guid_uint8_4
            0x23,  # guid_uint8_5
            0x45,  # guid_uint8_6
            0x67,  # guid_uint8_7
        )
        return contents

    def test_init(self, mock_header, sample_data):
        contents = sample_data
        # Test initialization of GuidEventRecord
        guid_event = GuidEventRecord(mock_header, contents)

        assert guid_event.progress_id == 0x1234
        assert guid_event.apic_id == 0x56789ABC
        assert guid_event.timestamp == 0xABCDEF0123456789
        assert guid_event.guid_uint32 == 0xDEADBEEF
        assert guid_event.guid_uint16_0 == 0xBEEF
        assert guid_event.guid_uint16_1 == 0xFEED
        assert guid_event.guid_uint8_0 == 0xDE
        assert guid_event.guid_uint8_1 == 0xAD
        assert guid_event.guid_uint8_2 == 0xBE
        assert guid_event.guid_uint8_3 == 0xEF
        assert guid_event.guid_uint8_4 == 0x01
        assert guid_event.guid_uint8_5 == 0x23
        assert guid_event.guid_uint8_6 == 0x45
        assert guid_event.guid_uint8_7 == 0x67

    def test_str(self, mock_header, sample_data):
        contents = sample_data
        # Test string representation of GuidEventRecord
        guid_event = GuidEventRecord(mock_header, contents)
        expected_str = (
            f"{mock_header}\n"
            f"  GUID Event Record Contents\n"
            f"------------------------------------------------------------------\n"
            f"  Progress ID : 0x1234\n"
            f"  Apic ID     : 0x56789ABC\n"
            f"  Timestamp   : 0xABCDEF0123456789\n"
            f"  GUID        : DEADBEEF-BEEF-FEED-DEAD-BEEF01234567\n"
        )
        assert str(guid_event) == expected_str

    def test_to_xml(self, mock_header, sample_data):
        contents = sample_data
        # Test XML conversion of GuidEventRecord
        guid_event = GuidEventRecord(mock_header, contents)
        xml_elem = guid_event.to_xml()

        # Check XML elements and attributes
        assert xml_elem.tag == "MockHeader"
        assert xml_elem.find("ProgressID").get("Value") == "0x1234"
        assert xml_elem.find("ApicID").get("Value") == "0x56789ABC"
        assert xml_elem.find("Timestamp").get("RawValue") == "0xABCDEF0123456789"
        assert (
            xml_elem.find("Timestamp").get("ValueInMilliseconds")
            == "12379813738877.119141"
        )
        assert (
            xml_elem.find("GUID").get("Value")
            == "DEADBEEF-BEEF-FEED-DEAD-BEEF-0123-4567"
        )


class TestDynamicStringEventRecord:

    @pytest.fixture
    def sample_bytes(self):
        return struct.pack(
            DynamicStringEventRecord.struct_format,
            0x1001,
            0x02,
            123456789,
            0xAABBCCDD,
            0x1122,
            0x3344,
            0x55,
            0x66,
            0x77,
            0x88,
            0x99,
            0xAA,
            0xBB,
            0xCC,
        )

    @pytest.fixture
    def valid_string_bytes(self):
        return b"TestEventNumOne\x00WithSomeJunkData"

    @pytest.fixture
    def unterminated_string_bytes(self):
        # No null terminator, which should trigger the error handling
        return b"InvalidEvent" + b"\xff" * 20

    @pytest.fixture
    def string_size(self):
        return 32

    def test_init_fields(
        self, mock_header, sample_bytes, valid_string_bytes, string_size
    ):
        record = DynamicStringEventRecord(
            mock_header, sample_bytes, valid_string_bytes, string_size
        )

        assert record.progress_id == 0x1001
        assert record.apic_id == 0x02
        assert record.timestamp == 123456789
        assert record.guid_uint32 == 0xAABBCCDD
        assert record.guid_uint16_0 == 0x1122
        assert record.guid_uint16_1 == 0x3344
        assert record.string.startswith("TestEventNumOne")

    def test_str_contains_expected(
        self, mock_header, sample_bytes, valid_string_bytes, string_size
    ):
        record = DynamicStringEventRecord(
            mock_header, sample_bytes, valid_string_bytes, string_size
        )
        s = str(record)

        assert "Progress ID" in s
        assert "0x1001" in s
        assert "Apic ID" in s
        assert "0x00000002" in s
        assert "TestEventNumOne" in s

    def test_to_xml_structure(
        self, mock_header, sample_bytes, valid_string_bytes, string_size
    ):
        record = DynamicStringEventRecord(
            mock_header, sample_bytes, valid_string_bytes, string_size
        )
        xml_elem = record.to_xml()

        assert xml_elem.tag == "MockHeader"
        assert xml_elem.find("ProgressID").get("Value") == "0x1001"
        assert xml_elem.find("ApicID").get("Value") == "0x2"
        assert xml_elem.find("Timestamp").get("RawValue") == "0x75BCD15"
        assert xml_elem.find("String").get("Value") == "TestEventNumOne"


class TestDualGuidStringEventRecord:
    def test_parses_all_fields_and_string(self, mock_header):
        # Field values
        progress_id = 0x0001
        apic_id = 0x00000002
        timestamp = 0x0000000000000003

        guid1 = (
            0x11111111,
            0x2222,
            0x3333,
            0x44,
            0x55,
            0x66,
            0x77,
            0x88,
            0x99,
            0xAA,
            0xBB,
        )
        guid2 = (
            0xCCCCCCCC,
            0xDDDD,
            0xEEEE,
            0xFF,
            0x00,
            0x11,
            0x22,
            0x33,
            0x44,
            0x55,
            0x66,
        )

        struct_format = "=HIQIHHBBBBBBBBIHHBBBBBBBB"
        packed_data = struct.pack(
            struct_format,
            progress_id,
            apic_id,
            timestamp,
            *guid1,
            *guid2,
        )

        test_string = b"TestEvent\x00WithJunkData"
        string_size = len(test_string)

        record = DualGuidStringEventRecord(
            mock_header, packed_data, test_string, string_size
        )

        assert record.header is mock_header
        assert record.progress_id == progress_id
        assert record.apic_id == apic_id
        assert record.timestamp == timestamp

        assert record.guid1_uint32 == guid1[0]
        assert record.guid1_uint16_0 == guid1[1]
        assert record.guid1_uint16_1 == guid1[2]
        assert [
            record.guid1_uint8_0,
            record.guid1_uint8_1,
            record.guid1_uint8_2,
            record.guid1_uint8_3,
            record.guid1_uint8_4,
            record.guid1_uint8_5,
            record.guid1_uint8_6,
            record.guid1_uint8_7,
        ] == list(guid1[3:])

        assert record.guid2_uint32 == guid2[0]
        assert record.guid2_uint16_0 == guid2[1]
        assert record.guid2_uint16_1 == guid2[2]
        assert [
            record.guid2_uint8_0,
            record.guid2_uint8_1,
            record.guid2_uint8_2,
            record.guid2_uint8_3,
            record.guid2_uint8_4,
            record.guid2_uint8_5,
            record.guid2_uint8_6,
            record.guid2_uint8_7,
        ] == list(guid2[3:])

        assert record.string == "TestEvent"

    def test_str_contains_all_fields(self, mock_header):
        progress_id = 0x1234
        apic_id = 0x56789ABC
        timestamp = 0x0123456789ABCDEF

        guid1 = (
            0xAAAAAAAA,
            0xBBBB,
            0xCCCC,
            0x01,
            0x02,
            0x03,
            0x04,
            0x05,
            0x06,
            0x07,
            0x08,
        )
        guid2 = (
            0x99999999,
            0x8888,
            0x7777,
            0x10,
            0x20,
            0x30,
            0x40,
            0x50,
            0x60,
            0x70,
            0x80,
        )

        packed_data = struct.pack(
            DualGuidStringEventRecord.struct_format,
            progress_id,
            apic_id,
            timestamp,
            *guid1,
            *guid2,
        )

        test_string = b"MyEvent\x00Extra"
        record = DualGuidStringEventRecord(
            mock_header, packed_data, test_string, len(test_string)
        )

        output = str(record)
        assert "Progress ID : 0x1234" in output
        assert "Apic ID     : 0x56789ABC" in output
        assert "Timestamp   : 0x0123456789ABCDEF" in output
        assert "GUID1       : AAAAAAAA-BBBB-CCCC-0102-030405060708" in output
        assert "GUID2       : 99999999-8888-7777-1020-304050607080" in output
        assert "String      : MyEvent" in output

    def test_to_xml(self, mock_header):
        packed_data = struct.pack(
            DualGuidStringEventRecord.struct_format,
            0x1,
            0x2,
            0x3,
            0x4,
            0x5,
            0x6,
            0x7,
            0x8,
            0x9,
            0xA,
            0xB,
            0xC,
            0xD,
            0xE,
            0xF,
            0x10,
            0x11,
            0x12,
            0x13,
            0x14,
            0x15,
            0x16,
            0x17,
            0x18,
            0x19,
        )
        test_string = b"BootMsg\x00"
        record = DualGuidStringEventRecord(
            mock_header, packed_data, test_string, len(test_string)
        )

        xml = record.to_xml()
        assert xml.find("ProgressID").attrib["Value"] == "0x1"
        assert xml.find("ApicID").attrib["Value"] == "0x2"
        assert xml.find("Timestamp").attrib["RawValue"] == "0x3"
        assert xml.find("Timestamp").attrib["ValueInMilliseconds"] == "0.000003"
        assert (
            xml.find("GUID1").attrib["Value"] == "00000004-0005-0006-0708090A0B0C0D0E"
        )
        assert (
            xml.find("GUID2").attrib["Value"] == "0000000F-0010-0011-1213141516171819"
        )
        assert xml.find("String").attrib["Value"] == "BootMsg"


class TestGuidQwordEventRecord:
    @pytest.fixture
    def sample_bytes(self):
        # Use dummy values for all fields
        values = (
            0x1234,  # progress_id (H)
            0x56789ABC,  # apic_id (I)
            0x123456789ABCDEF0,  # timestamp (Q)
            0xDEADBEEF,  # guid_uint32 (I)
            0xCAFE,  # guid_uint16_0 (H)
            0xBABE,  # guid_uint16_1 (H)
            0x01,
            0x02,
            0x03,
            0x04,  # guid_uint8_0 to _3 (B)
            0x05,
            0x06,
            0x07,
            0x08,  # guid_uint8_4 to _7 (B)
            0x0FEDCBA987654321,  # qword (Q)
        )
        packed = struct.pack(GuidQwordEventRecord.struct_format, *values)
        return packed

    def test_guid_qword_event_record_fields(self, mock_header, sample_bytes):
        record = GuidQwordEventRecord(mock_header, sample_bytes)

        assert record.progress_id == 0x1234
        assert record.apic_id == 0x56789ABC
        assert record.timestamp == 0x123456789ABCDEF0
        assert record.guid_uint32 == 0xDEADBEEF
        assert record.guid_uint16_0 == 0xCAFE
        assert record.guid_uint16_1 == 0xBABE
        assert record.guid_uint8_0 == 0x01
        assert record.guid_uint8_1 == 0x02
        assert record.guid_uint8_2 == 0x03
        assert record.guid_uint8_3 == 0x04
        assert record.guid_uint8_4 == 0x05
        assert record.guid_uint8_5 == 0x06
        assert record.guid_uint8_6 == 0x07
        assert record.guid_uint8_7 == 0x08
        assert record.qword == 0x0FEDCBA987654321

    def test_guid_qword_event_record_str(self, mock_header, sample_bytes):
        record = GuidQwordEventRecord(mock_header, sample_bytes)
        result = str(record)

        assert "Progress ID : 0x1234" in result
        assert "Apic ID     : 0x56789ABC" in result
        assert "Timestamp   : 0x123456789ABCDEF0" in result
        assert "GUID        : DEADBEEF-CAFE-BABE-0102030405060708" in result
        assert "Qword       : 0x0FEDCBA987654321" in result
        assert "MockHeader" in result

    def test_guid_qword_event_record_to_xml(self, mock_header, sample_bytes):
        record = GuidQwordEventRecord(mock_header, sample_bytes)
        xml = record.to_xml()

        assert xml.tag == "MockHeader"

        progress_id = xml.find("ProgressID")
        assert progress_id is not None
        assert progress_id.attrib["Value"] == "0x1234"

        apic_id = xml.find("ApicID")
        assert apic_id is not None
        assert apic_id.attrib["Value"] == "0x56789ABC"

        timestamp = xml.find("Timestamp")
        assert timestamp is not None
        assert timestamp.attrib["RawValue"] == "0x123456789ABCDEF0"
        assert float(timestamp.attrib["ValueInMilliseconds"]) == pytest.approx(
            0x123456789ABCDEF0 / 1_000_000.0, rel=1e-9
        )

        guid = xml.find("GUID")
        assert guid is not None
        assert guid.attrib["Value"] == "DEADBEEF-CAFE-BABE-0102030405060708"

        qword = xml.find("Qword")
        assert qword is not None
        assert qword.attrib["Value"] == "0xFEDCBA987654321"


class TestGuidQwordStringEventRecord:
    def test_parses_all_fields_and_string(self, mock_header):
        progress_id = 0x1234
        apic_id = 0x56789ABC
        timestamp = 0x0123456789ABCDEF

        guid = (
            0xAAAAAAAA,
            0xBBBB,
            0xCCCC,
            0x01,
            0x02,
            0x03,
            0x04,
            0x05,
            0x06,
            0x07,
            0x08,
        )

        qword = 0x1122334455667788

        struct_format = GuidQwordStringEventRecord.struct_format
        packed_data = struct.pack(
            struct_format, progress_id, apic_id, timestamp, *guid, qword
        )

        string_data = b"TestMessage\x00ExtraGarbage"
        record = GuidQwordStringEventRecord(
            mock_header, packed_data, string_data, len(string_data)
        )

        assert record.header is mock_header
        assert record.progress_id == progress_id
        assert record.apic_id == apic_id
        assert record.timestamp == timestamp

        assert record.guid_uint32 == guid[0]
        assert record.guid_uint16_0 == guid[1]
        assert record.guid_uint16_1 == guid[2]
        assert [
            record.guid_uint8_0,
            record.guid_uint8_1,
            record.guid_uint8_2,
            record.guid_uint8_3,
            record.guid_uint8_4,
            record.guid_uint8_5,
            record.guid_uint8_6,
            record.guid_uint8_7,
        ] == list(guid[3:])

        assert record.qword == qword
        assert record.string == "TestMessage"

    def test_str_contains_all_fields(self, mock_header):
        values = {
            "progress_id": 0xABCD,
            "apic_id": 0x12345678,
            "timestamp": 0x0A0B0C0D0E0F1011,
            "guid": (
                0x11112222,
                0x3333,
                0x4444,
                0xAA,
                0xBB,
                0xCC,
                0xDD,
                0xEE,
                0xFF,
                0x00,
                0x11,
            ),
            "qword": 0xDEADBEEFCAFEBABE,
        }

        packed_data = struct.pack(
            GuidQwordStringEventRecord.struct_format,
            values["progress_id"],
            values["apic_id"],
            values["timestamp"],
            *values["guid"],
            values["qword"],
        )

        string_data = b"BootStage\x00Ignore"
        record = GuidQwordStringEventRecord(
            mock_header, packed_data, string_data, len(string_data)
        )

        output = str(record)
        assert "Progress ID : 0xABCD" in output
        assert "Apic ID     : 0x12345678" in output
        assert "Timestamp   : 0x0A0B0C0D0E0F1011" in output
        assert "GUID        : 11112222-3333-4444-AABBCCDDEEFF0011" in output
        assert "Qword       : 0xDEADBEEFCAFEBABE" in output
        assert "String      : BootStage" in output

    def test_to_xml(self, mock_header):
        packed_data = struct.pack(
            GuidQwordStringEventRecord.struct_format,
            0x1,
            0x2,
            0x3,
            0x4,
            0x5,
            0x6,
            0x7,
            0x8,
            0x9,
            0xA,
            0xB,
            0xC,
            0xD,
            0xE,
            0xF0F0F0F0F0F0F0F0,
        )

        test_string = b"Phase\x00Trailing"
        record = GuidQwordStringEventRecord(
            mock_header, packed_data, test_string, len(test_string)
        )

        xml = record.to_xml()

        assert xml.find("ProgressID").attrib["Value"] == "0x1"
        assert xml.find("ApicID").attrib["Value"] == "0x2"
        assert xml.find("Timestamp").attrib["RawValue"] == "0x3"
        assert xml.find("Timestamp").attrib["ValueInMilliseconds"] == "0.000003"
        assert xml.find("GUID").attrib["Value"] == "00000004-0005-0006-0708090A0B0C0D0E"
        assert xml.find("Qword").attrib["Value"] == "0xF0F0F0F0F0F0F0F0"
        assert xml.find("String").attrib["Value"] == "Phase"


class TestSystemFirmwareTable:

    # mock init
    @pytest.fixture
    def system_firmware_table(self):
        with patch.object(SystemFirmwareTable, "__init__", return_value=None):
            instance = SystemFirmwareTable()
            return instance

    def test_get_system_firmware_table_is_none(self, system_firmware_table):
        system_firmware_table._get_system_firmware_table = None
        error_code, table_data, msg = system_firmware_table.get_acpi_table(b"TEST")
        assert error_code == -20
        assert table_data is None
        assert msg == "GetSystemFirmwareTable is None"

    def test_get_acpi_table_equal_lengths(self, system_firmware_table):
        mock_get_table = Mock(side_effect=[1200, 1200])
        system_firmware_table._get_system_firmware_table = mock_get_table

        with (
            patch("ctypes.windll.kernel32.GetLastError", return_value=0),
            patch("ctypes.WinError", return_value="WinErrorMock"),
        ):
            error_code, table_data, msg = system_firmware_table.get_acpi_table(b"FACP")

        assert error_code == 0
        assert table_data is None
        assert msg == "Length = 0"
        assert mock_get_table.call_count == 2

    def test_get_acpi_table_length_mismatch(self, system_firmware_table):
        mock_get_table = Mock(
            side_effect=[1200, 800]
        )  # mismatch between length and length2
        system_firmware_table._get_system_firmware_table = mock_get_table

        with (
            patch("ctypes.windll.kernel32.GetLastError", return_value=1234),
            patch("ctypes.WinError", return_value="WinErrorMock") as mock_win_error,
        ):
            error_code, table_data, msg = system_firmware_table.get_acpi_table(b"FACP")

        assert error_code == 1234
        assert table_data is None

    def test_get_acpi_table_length_less_than_1000(self, system_firmware_table):
        mock_get_table = Mock(side_effect=[1200, 1200])
        system_firmware_table._get_system_firmware_table = mock_get_table

        with (
            patch("ctypes.windll.kernel32.GetLastError", return_value=0),
            patch("ctypes.WinError", return_value="WinErrorMock"),
        ):
            error_code, table_data, msg = system_firmware_table.get_acpi_table(b"FACP")

        assert error_code == 0
        assert table_data is None
        assert msg == "Length = 0"
        assert mock_get_table.call_count == 2

    def test_get_acpi_table_fixed_length(self, system_firmware_table):
        system_firmware_table._get_system_firmware_table = Mock(return_value=500)
        error_code, table_data, msg = system_firmware_table.get_acpi_table(b"TEST")
        assert error_code == 0
        assert isinstance(table_data, bytes)
        assert len(table_data) == 500
        assert msg is None

    def test_get_fbpt_nonzero_status(self, system_firmware_table):
        system_firmware_table._nt_query_system_information = Mock(return_value=1234)
        status, param1 = system_firmware_table.get_fbpt()
        assert status == 1
        assert param1 is None

    def test_get_fbpt_success(self, system_firmware_table):
        system_firmware_table._nt_query_system_information = Mock(
            side_effect=[0xC0000004, 0]
        )
        status, param1 = system_firmware_table.get_fbpt()
        assert status == 0

    @pytest.mark.parametrize(
        "record_type,record_class",
        [
            (
                FIRMWARE_BASIC_BOOT_PERFORMANCE_DATA_EVENT_TYPE,
                FwBasicBootPerformanceDataRecord,
            ),
            (GUID_EVENT_TYPE, GuidEventRecord),
            (GUID_QWORD_EVENT_TYPE, GuidQwordEventRecord),
            (FPDT_GUID_QWORD_EVENT_TYPE, GuidQwordEventRecord),
        ],
    )
    def test_fbpt_parsing_factory_nonstring_record_types(
        self, record_type, record_class
    ):
        record_length = FbptRecordHeader.size + record_class.size
        revision = 1

        mock_header_bytes = (
            record_type.to_bytes(2, "little")
            + record_length.to_bytes(1, "little")
            + revision.to_bytes(1, "little")
        )

        mock_record_bytes = b"\x01" * (record_class.size)
        eof = b""
        read_sequence = [mock_header_bytes, mock_record_bytes, eof]

        # Mock file and perform parsing
        mock_file = Mock()
        mock_file.read = Mock(side_effect=read_sequence)

        records_list = []
        result = fbpt_parsing_factory(mock_file, records_list)

        # Assertions
        assert result == 0
        assert len(records_list) == 1
        assert isinstance(records_list[0], record_class)
        assert records_list[0].header.performance_record_type == record_type

    @pytest.mark.parametrize(
        "record_type,record_class",
        [
            (DYNAMIC_STRING_EVENT_TYPE, DynamicStringEventRecord),
            (FPDT_DYNAMIC_STRING_EVENT_TYPE, DynamicStringEventRecord),
            (DUAL_GUID_STRING_EVENT_TYPE, DualGuidStringEventRecord),
            (FPDT_DUAL_GUID_STRING_EVENT_TYPE, DualGuidStringEventRecord),
            (GUID_QWORD_STRING_EVENT_TYPE, GuidQwordStringEventRecord),
            (FPDT_GUID_QWORD_STRING_EVENT_TYPE, GuidQwordStringEventRecord),
        ],
    )
    def test_fbpt_parsing_factory_all_record_types(self, record_type, record_class):
        record_size = record_class.size
        record_length = FbptRecordHeader.size + record_size + 5  # 4 = string size
        mock_header_bytes = (
            record_type.to_bytes(2, "little")
            + record_length.to_bytes(1, "little")
            + (1).to_bytes(1, "little")
        )
        mock_record_bytes = b"\x01" * record_size

        string_data = b"TEST\x00"
        string_size = (4).to_bytes(4, "little")
        read_sequence = [mock_header_bytes, mock_record_bytes, string_data, b""]

        mock_file = Mock()
        mock_file.read = Mock(side_effect=read_sequence)
        records_list = []

        result = fbpt_parsing_factory(mock_file, records_list)

        assert result == 0
        assert len(records_list) == 1
        assert isinstance(records_list[0], record_class)
        assert records_list[0].header.performance_record_type == record_type


class TestGetUefiVersionGetModel:

    # mock wmi
    @pytest.fixture
    def mock_wmi(self):
        mock_wmi = types.ModuleType("wmi")
        return mock_wmi

    def test_get_uefi_version_success_and_failure(self, mock_wmi):
        mock_bios = MagicMock()
        mock_bios.SMBIOSBIOSVersion = "UEFI-TEST-VERSION"
        mock_WMI_instance = MagicMock()
        mock_WMI_instance.Win32_BIOS.return_value = [mock_bios]
        mock_wmi.WMI = MagicMock(return_value=mock_WMI_instance)
        with patch.dict(sys.modules, {"wmi": mock_wmi}):
            result = get_uefi_version()
            assert result == "UEFI-TEST-VERSION"

        mock_wmi.WMI = MagicMock(side_effect=Exception("Simulated failure"))
        with patch.dict(sys.modules, {"wmi": mock_wmi}):
            result = get_uefi_version()
            assert result == "Unknown"

    def test_get_model_success_and_failure(self, mock_wmi):
        mock_wmi = types.ModuleType("wmi")
        mock_model = MagicMock()
        mock_model.Model = "TestModel123"
        mock_wmi.WMI = MagicMock(
            return_value=MagicMock(
                Win32_ComputerSystem=MagicMock(return_value=[mock_model])
            )
        )

        with patch.dict(sys.modules, {"wmi": mock_wmi}):
            result = get_model()
            assert result == "TestModel123"

    def test_get_model_failure(self, mock_wmi):
        # Simulate a failure in wmi.WMI
        mock_wmi = types.ModuleType("wmi")
        mock_wmi.WMI = MagicMock(side_effect=Exception("Simulated WMI failure"))

        with patch.dict(sys.modules, {"wmi": mock_wmi}):
            result = get_model()
            assert result == "Unknown"


class TestParser:
    def mock_parser_app(
        self,
        mock_handle_output_file=None,
        mock_handle_input_file=None,
        mock_get_uefi_version_model=None,
        mock_write_text_header=None,
        mock_write_xml_header=None,
        output_text_file="test_output.txt",
        output_xml_file="test_output.xml",
        input_fbpt_bin="FBPT_TestModel_TestUEFI.bin",
    ):
        if mock_handle_output_file is None:
            mock_handle_output_file = mock.Mock(spec=["write", "close"])
        if not mock_handle_input_file:
            mock_handle_input_file = mock.Mock()
        if not mock_get_uefi_version_model:
            mock_get_uefi_version_model = mock.Mock(
                return_value=("TestUEFI", "TestModel")
            )
        if not mock_write_text_header:
            mock_write_text_header = mock.Mock()
        if not mock_write_xml_header:
            mock_write_xml_header = mock.Mock(spec=["append"])

        mock_parse_args = mock.Mock(
            return_value=mock.Mock(
                output_text_file=output_text_file,
                output_xml_file=output_xml_file,
                input_fbpt_bin=input_fbpt_bin,
            )
        )

        with (
            mock.patch.object(ParserApp, "set_up_logging"),
            mock.patch.object(ParserApp, "handle_output_file", mock_handle_output_file),
            mock.patch.object(ParserApp, "handle_input_file", mock_handle_input_file),
            mock.patch.object(
                ParserApp,
                "get_uefi_version_model",
                mock_get_uefi_version_model,
            ),
            mock.patch.object(ParserApp, "write_text_header"),
            mock.patch.object(ParserApp, "write_xml_header", return_value=mock.Mock()),
            mock.patch.object(
                edk2toolext.perf.fpdt_parser.argparse.ArgumentParser,
                "parse_args",
                mock_parse_args,
            ),
        ):
            # Create instance without triggering real side effects
            app = ParserApp()

            # Override self.options with a mock
            app.options = mock.Mock(
                output_text_file=output_text_file,
                output_xml_file=output_xml_file,
                input_fbpt_bin=input_fbpt_bin,
            )

            app.text_log = mock.Mock(spec=["write", "close"])
            app.xml_tree = mock.Mock(spec=["append"])

            return app

    def test_handle_output_file(self):
        mock_app = self.mock_parser_app(
            mock_handle_output_file=ParserApp.handle_output_file
        )
        assert mock_app.text_log is not None

    def test_handle_output_file_xml_too_short(self):
        with pytest.raises(ValueError):
            self.mock_parser_app(
                mock_handle_output_file=ParserApp.handle_output_file,
                output_xml_file="e",
            )

    def test_handle_output_file_text_too_short(self):
        with pytest.raises(ValueError):
            self.mock_parser_app(
                mock_handle_output_file=ParserApp.handle_output_file,
                output_text_file="e",
            )

    def test_handle_input_file_too_short(self):
        with pytest.raises(ValueError):
            self.mock_parser_app(
                mock_handle_input_file=ParserApp.handle_input_file, input_fbpt_bin="e"
            )

    def test_handle_input_file_invalid_file(self):
        with mock.patch("os.path.isfile", return_value=False):
            with pytest.raises(ValueError):
                self.mock_parser_app(
                    mock_handle_input_file=ParserApp.handle_input_file,
                )

    def test_handle_input_file_invalid_file(self):
        with mock.patch("os.path.isfile", return_value=False):
            with pytest.raises(ValueError):
                self.mock_parser_app(
                    mock_handle_input_file=ParserApp.handle_input_file,
                )

    def test_get_uefi_model_no_input(self):
        with (
            mock.patch(
                "edk2toolext.perf.fpdt_parser.get_uefi_version", return_value="Uefi1"
            ),
            mock.patch("edk2toolext.perf.fpdt_parser.get_model", return_value="Model1"),
        ):
            mock_app = self.mock_parser_app(
                mock_get_uefi_version_model=ParserApp.get_uefi_version_model,
                input_fbpt_bin=None,
            )
            assert mock_app.uefi_version == "Uefi1"
            assert mock_app.model == "Model1"

    def test_get_uefi_model_bad_file_name(self):
        mock_app = self.mock_parser_app(
            mock_get_uefi_version_model=ParserApp.get_uefi_version_model,
            input_fbpt_bin="FBPT.bin",
        )
        assert mock_app.uefi_version == "N/A"
        assert mock_app.model == "N/A"

    def test_get_uefi_model_complete_file_name(self):
        mock_app = self.mock_parser_app(
            mock_get_uefi_version_model=ParserApp.get_uefi_version_model,
            input_fbpt_bin="FBPT_TestUEFI_1.2.3.bin",
        )
        assert mock_app.uefi_version == "TestUEFI"
        assert mock_app.model == "1.2.3"

    def test_text_write(self):
        mock_app = self.mock_parser_app()
        mock_app.write_text_header()
        expected_text = (
            "  Platform Information\n"
            "------------------------------------------------------------------\n"
            "UEFI Version : TestUEFI\n"
            "  Model        : TestModel\n"
        )
        mock_app.text_log.write.assert_called_once_with(expected_text)

    def test_write_xml(self):
        mock_app = self.mock_parser_app()
        mock_app.datetime = mock.Mock()
        mock_app.datetime.now.return_value = datetime.datetime(2025, 5, 6)
        xml_tree = mock_app.write_xml_header()
        assert xml_tree.tag == "FpdtParserData"

        # Check the child elements and their attributes
        uefi_version_elem = xml_tree.find("UEFIVersion")
        assert uefi_version_elem is not None
        assert uefi_version_elem.get("Value") == "TestUEFI"

        model_elem = xml_tree.find("Model")
        assert model_elem is not None
        assert model_elem.get("Value") == "TestModel"

        date_collected_elem = xml_tree.find("DateCollected")
        assert date_collected_elem is not None
        assert date_collected_elem.get("Value") == "5/6/2025"  # Mocked date

        fpdt_parser_version_elem = xml_tree.find("FpdtParserVersion")
        assert fpdt_parser_version_elem is not None
        assert fpdt_parser_version_elem.get("Value") == FPDT_PARSER_VER

    def test_write_fpdt_header(self):
        mock_app = self.mock_parser_app(input_fbpt_bin=None)
        mock_table = mock.Mock()
        mock_table.get_acpi_table.return_value = (0, b"\x00" * 128, "mock error")

        mock_app.write_fpdt_header(mock_table)

        # Check `write` indirectly by making sure it's called with the correct strings
        all_calls = mock_app.text_log.write.call_args_list
        assert "ACPI Table Header" in all_calls[0][0][0]
        assert "Firmware Basic Boot Performance Record" in all_calls[1][0][0]

    def test_find_fbpt_file_get_fbpt_failure(self):
        with pytest.raises(EnvironmentError):
            mock_app = self.mock_parser_app(input_fbpt_bin=None)
            mock_table = mock.Mock()
            mock_table.get_fbpt.return_value = (1, [])
            mock_app.find_fbpt_file(mock_table)

    def test_find_fbpt_file_success_no_input_file(self):
        mock_app = self.mock_parser_app(input_fbpt_bin=None)
        mock_table = mock.Mock()
        mock_table.get_fbpt.return_value = (0, b"valid_fbpt_buffer")
        mock_open = mock.mock_open()
        with mock.patch("builtins.open", mock_open):
            mock_app.find_fbpt_file(mock_table)

            mock_open.assert_any_call(
                "FBPT.BIN", "wb"
            )  # make sure open occured to correct file

    def test_find_fbpt_file_success_named_input_file(self):
        mock_app = self.mock_parser_app()
        mock_table = mock.Mock()
        mock_table.get_fbpt.return_value = (0, b"valid_fbpt_buffer")
        mock_open = mock.mock_open()
        with mock.patch("builtins.open", mock_open):
            mock_app.find_fbpt_file(mock_table)

            mock_open.assert_any_call(
                "FBPT_TestModel_TestUEFI.bin", "rb"
            )  # make sure open occured to correct file

    def test_write_fbpt(self):
        mock_app = self.mock_parser_app()
        mock_fbpt_file = mock.Mock()
        mock_fbpt_file.read.return_value = b"fake_fbpt_header_data"
        mock_header = MagicMock(spec=FwBasicBootPerformanceTableHeader)
        mock_header.to_xml.return_value = "<fbpt_header_xml>fake_xml</fbpt_header_xml>"
        mock_header.__str__.return_value = "Fake FBPT Header String"
        with mock.patch.object(
            FwBasicBootPerformanceTableHeader, "__new__", return_value=mock_header
        ):
            mock_app.write_fbpt(mock_fbpt_file)
            mock_app.text_log.write.assert_called_once_with("Fake FBPT Header String")
            mock_app.xml_tree.append.assert_called_once_with(
                "<fbpt_header_xml>fake_xml</fbpt_header_xml>"
            )

    def test_gather_fbpt_records_parse_failure(self):
        mock_app = self.mock_parser_app()
        mock_fbpt_file = mock.Mock()

        def mock_parsing_factory_side_effect(fbpt_file, fbpt_records_list):
            mock_record = mock.Mock()
            fbpt_records_list.append(mock_record)
            return 0

        with mock.patch(
            "edk2toolext.perf.fpdt_parser.fbpt_parsing_factory",
            side_effect=mock_parsing_factory_side_effect,
        ):
            fbpt_records = mock_app.gather_fbpt_records(mock_fbpt_file)
            assert len(fbpt_records) == 1

    def test_write_records(self):
        mock_app = self.mock_parser_app()
        mock_record = MagicMock()
        mock_record.to_xml.return_value = "<Record1></Record1>"
        mock_record.__str__.return_value = "Record1"
        fbpt_records_list = [mock_record]
        with (
            mock.patch("builtins.open", mock.mock_open()),
            mock.patch("xml.etree.ElementTree.tostring"),
        ):
            result = mock_app.write_records(fbpt_records_list)
            assert result == 1
            mock_app.xml_tree.append.assert_any_call("<Record1></Record1>")
            mock_app.text_log.write.assert_any_call("Record1")


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_files():
    yield  # run the test
    # After test completes, delete any matching files
    perf_dir = Path("edk2toolext") / "perf"
    for pattern in [
        "FBPT.BIN",
        "test_output.*",
        "*.xml",
        "*.bin",
        "*.txt",
    ]:
        for file in perf_dir.glob(pattern):
            try:
                os.remove(file)
            except OSError:
                pass  # ignore if file doesn't exist
