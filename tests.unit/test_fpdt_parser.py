import struct
import xml.etree.ElementTree as ET
import pytest

from edk2toolext.perf.fpdt_parser import (
    AcpiTableHeader,
    FwBasicBootPerformanceRecord,
    FwBasicBootPerformanceTableHeader,
    FbptRecordHeader,
    FwBasicBootPerformanceDataRecord,
    GuidEventRecord,
    DynamicStringEventRecord,
    DualGuidStringEventRecord,
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
)

# ---------------------------------------
# ACPI TABLE HEADER
# ---------------------------------------


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


# ---------------------------------------
# FW BASIC BOOT PERFORMANCE RECORD
# ---------------------------------------


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


# ---------------------------------------
# FBPT TABLE HEADER
# ---------------------------------------


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
