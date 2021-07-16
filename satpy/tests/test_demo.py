#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2019-2021 Satpy developers
#
# This file is part of satpy.
#
# satpy is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# satpy is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# satpy.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for the satpy.demo module."""
import io
import os
import sys
import tarfile
import unittest
from unittest import mock


class _GlobHelper(object):
    """Create side effect function for mocking gcsfs glob method."""

    def __init__(self, num_results):
        """Initialize side_effect function for mocking gcsfs glob method.

        Args:
            num_results (int or list): Number of results for each glob call
                to return. If a list then number of results per call. The
                last number is used for any additional calls.

        """
        self.current_call = 0
        if not isinstance(num_results, (list, tuple)):
            num_results = [num_results]
        self.num_results = num_results

    def __call__(self, pattern):
        """Mimic glob by being used as the side effect function."""
        try:
            num_results = self.num_results[self.current_call]
        except IndexError:
            num_results = self.num_results[-1]
        self.current_call += 1
        return [pattern + '.{:03d}'.format(idx) for idx in range(num_results)]


class TestDemo(unittest.TestCase):
    """Test demo data download functions."""

    def setUp(self):
        """Create temporary directory to save files to."""
        import tempfile
        self.base_dir = tempfile.mkdtemp()
        self.prev_dir = os.getcwd()
        os.chdir(self.base_dir)

    def tearDown(self):
        """Remove the temporary directory created for a test."""
        os.chdir(self.prev_dir)
        try:
            import shutil
            shutil.rmtree(self.base_dir, ignore_errors=True)
        except OSError:
            pass

    @mock.patch('satpy.demo._google_cloud_platform.gcsfs')
    def test_get_us_midlatitude_cyclone_abi(self, gcsfs_mod):
        """Test data download function."""
        from satpy.demo import get_us_midlatitude_cyclone_abi
        gcsfs_mod.GCSFileSystem = mock.MagicMock()
        gcsfs_inst = mock.MagicMock()
        gcsfs_mod.GCSFileSystem.return_value = gcsfs_inst
        gcsfs_inst.glob.return_value = ['a.nc', 'b.nc']
        # expected 16 files, got 2
        self.assertRaises(AssertionError, get_us_midlatitude_cyclone_abi)
        # unknown access method
        self.assertRaises(NotImplementedError, get_us_midlatitude_cyclone_abi, method='unknown')

        gcsfs_inst.glob.return_value = ['a.nc'] * 16
        filenames = get_us_midlatitude_cyclone_abi()
        expected = os.path.join('.', 'abi_l1b', '20190314_us_midlatitude_cyclone', 'a.nc')
        for fn in filenames:
            self.assertEqual(expected, fn)

    @mock.patch('satpy.demo._google_cloud_platform.gcsfs')
    def test_get_hurricane_florence_abi(self, gcsfs_mod):
        """Test data download function."""
        from satpy.demo import get_hurricane_florence_abi
        gcsfs_mod.GCSFileSystem = mock.MagicMock()
        gcsfs_inst = mock.MagicMock()
        gcsfs_mod.GCSFileSystem.return_value = gcsfs_inst
        # only return 5 results total
        gcsfs_inst.glob.side_effect = _GlobHelper([5, 0])
        # expected 16 files * 10 frames, got 16 * 5
        self.assertRaises(AssertionError, get_hurricane_florence_abi)
        self.assertRaises(NotImplementedError, get_hurricane_florence_abi, method='unknown')

        gcsfs_inst.glob.side_effect = _GlobHelper([int(240 / 16), 0, 0, 0] * 16)
        filenames = get_hurricane_florence_abi()
        self.assertEqual(10 * 16, len(filenames))

        gcsfs_inst.glob.side_effect = _GlobHelper([int(240 / 16), 0, 0, 0] * 16)
        filenames = get_hurricane_florence_abi(channels=[2, 3, 4])
        self.assertEqual(10 * 3, len(filenames))

        gcsfs_inst.glob.side_effect = _GlobHelper([int(240 / 16), 0, 0, 0] * 16)
        filenames = get_hurricane_florence_abi(channels=[2, 3, 4], num_frames=5)
        self.assertEqual(5 * 3, len(filenames))

        gcsfs_inst.glob.side_effect = _GlobHelper([int(240 / 16), 0, 0, 0] * 16)
        filenames = get_hurricane_florence_abi(num_frames=5)
        self.assertEqual(5 * 16, len(filenames))


class TestGCPUtils(unittest.TestCase):
    """Test Google Cloud Platform utilities."""

    @mock.patch('satpy.demo._google_cloud_platform.urlopen')
    def test_is_gcp_instance(self, uo):
        """Test is_google_cloud_instance."""
        from satpy.demo._google_cloud_platform import is_google_cloud_instance, URLError
        uo.side_effect = URLError("Test Environment")
        self.assertFalse(is_google_cloud_instance())

    @mock.patch('satpy.demo._google_cloud_platform.gcsfs')
    def test_get_bucket_files(self, gcsfs_mod):
        """Test get_bucket_files basic cases."""
        from satpy.demo._google_cloud_platform import get_bucket_files
        gcsfs_mod.GCSFileSystem = mock.MagicMock()
        gcsfs_inst = mock.MagicMock()
        gcsfs_mod.GCSFileSystem.return_value = gcsfs_inst
        gcsfs_inst.glob.return_value = ['a.nc', 'b.nc']
        filenames = get_bucket_files('*.nc', '.')
        expected = [os.path.join('.', 'a.nc'), os.path.join('.', 'b.nc')]
        self.assertEqual(expected, filenames)

        gcsfs_inst.glob.side_effect = _GlobHelper(10)
        filenames = get_bucket_files(['*.nc', '*.txt'], '.', pattern_slice=slice(2, 5))
        self.assertEqual(len(filenames), 3 * 2)
        gcsfs_inst.glob.side_effect = None  # reset mock side effect

        gcsfs_inst.glob.return_value = ['a.nc', 'b.nc']
        self.assertRaises(OSError, get_bucket_files, '*.nc', 'does_not_exist')

        open('a.nc', 'w').close()  # touch the file
        gcsfs_inst.get.reset_mock()
        gcsfs_inst.glob.return_value = ['a.nc']
        filenames = get_bucket_files('*.nc', '.')
        self.assertEqual([os.path.join('.', 'a.nc')], filenames)
        gcsfs_inst.get.assert_not_called()

        # force redownload
        gcsfs_inst.get.reset_mock()
        gcsfs_inst.glob.return_value = ['a.nc']
        filenames = get_bucket_files('*.nc', '.', force=True)
        self.assertEqual([os.path.join('.', 'a.nc')], filenames)
        gcsfs_inst.get.assert_called_once()

        # if we don't get any results then we expect an exception
        gcsfs_inst.get.reset_mock()
        gcsfs_inst.glob.return_value = []
        self.assertRaises(OSError, get_bucket_files, '*.nc', '.')

    @mock.patch('satpy.demo._google_cloud_platform.gcsfs', None)
    def test_no_gcsfs(self):
        """Test that 'gcsfs' is required."""
        from satpy.demo._google_cloud_platform import get_bucket_files
        self.assertRaises(RuntimeError, get_bucket_files, '*.nc', '.')


class TestAHIDemoDownload:
    """Test the AHI demo data download."""

    @mock.patch.dict(sys.modules, {'s3fs': mock.MagicMock()})
    def test_ahi_full_download(self):
        """Test that the himawari download works as expected."""
        from satpy.demo import download_typhoon_surigae_ahi
        from tempfile import gettempdir
        files = download_typhoon_surigae_ahi(base_dir=gettempdir())
        assert len(files) == 160

    @mock.patch.dict(sys.modules, {'s3fs': mock.MagicMock()})
    def test_ahi_partial_download(self):
        """Test that the himawari download works as expected."""
        from satpy.demo import download_typhoon_surigae_ahi
        from tempfile import gettempdir
        files = download_typhoon_surigae_ahi(base_dir=gettempdir(), segments=[4, 9], channels=[1, 2, 3])
        assert len(files) == 6


def test_fci_download(tmp_path, monkeypatch):
    """Test download of FCI test data."""
    from satpy.demo import download_fci_test_data
    monkeypatch.chdir(tmp_path)

    def fake_urlretrieve(url):
        # create a dummy tarfile
        fn = tmp_path / "tofu.tar.gz"
        fn.parent.mkdir(exist_ok=True, parents=True)

        with tarfile.open(fn, mode="x:gz") as tf:
            for i in range(3):
                with open(f"fci-rc{i:d}", "w"):
                    pass
                tf.addfile(tf.gettarinfo(name=f"fci-rc{i:d}"))
        return (os.fspath(fn), None)
    with mock.patch("urllib.request.urlretrieve", new=fake_urlretrieve):
        files = download_fci_test_data(tmp_path)
    assert len(files) == 3
    assert files == ["fci-rc0", "fci-rc1", "fci-rc2"]
    for f in files:
        assert os.path.exists(f)


class _FakeRequest:
    """Fake object to act like a requests return value when downloading a zip file."""

    def __init__(self, url, stream=None):
        self._filename = os.path.basename(url)
        self.headers = {}
        del stream  # just mimicking requests 'get'

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return

    def raise_for_status(self):
        return

    def _get_fake_viirs_sdr_bytesio(self):
        filelike_obj = io.BytesIO()
        filelike_obj.write(self._filename.encode("ascii"))
        filelike_obj.seek(0)
        return filelike_obj

    def iter_content(self, chunk_size):
        """Return generator of 'chunk_size' at a time."""
        bytes_io = self._get_fake_viirs_sdr_bytesio()
        x = bytes_io.read(chunk_size)
        while x:
            yield x
            x = bytes_io.read(chunk_size)


class TestVIIRSSDRDemoDownload:
    """Test VIIRS SDR downloading."""

    ALL_BAND_PREFIXES = ("SVI01", "SVI02", "SVI03", "SVI04", "SVI05",
                         "SVM01", "SVM02", "SVM03", "SVM04", "SVM05", "SVM06", "SVM07", "SVM08", "SVM09", "SVM10",
                         "SVM11", "SVM12", "SVM13", "SVM14", "SVM15", "SVM16",
                         "SVDNB")
    ALL_GEO_PREFIXES = ("GITCO", "GMTCO", "GDNBO")

    @mock.patch('satpy.demo.viirs_sdr.requests')
    def test_download(self, _requests, tmpdir):
        """Test downloading and re-downloading VIIRS SDR data."""
        from satpy.demo import get_viirs_sdr_20170128_1229
        _requests.get.side_effect = _FakeRequest
        files = get_viirs_sdr_20170128_1229(base_dir=str(tmpdir))
        assert len(files) == 10 * (16 + 5 + 1 + 3)  # 10 granules * (5 I bands + 16 M bands + 1 DNB + 3 geolocation)
        self._assert_bands_in_filenames_and_contents(self.ALL_BAND_PREFIXES + self.ALL_GEO_PREFIXES, files, 10)

        get_mock = mock.MagicMock()
        _requests.get.return_value = get_mock
        new_files = get_viirs_sdr_20170128_1229(base_dir=str(tmpdir))
        assert len(new_files) == 10 * (16 + 5 + 1 + 3)  # 10 granules * (5 I bands + 16 M bands + 1 DNB + 3 geolocation)
        get_mock.assert_not_called()
        assert new_files == files

    @mock.patch('satpy.demo.viirs_sdr.requests')
    def test_download_channels_num_granules_im(self, _requests, tmpdir):
        """Test downloading and re-downloading VIIRS SDR I/M data with select granules."""
        from satpy.demo import get_viirs_sdr_20170128_1229
        _requests.get.side_effect = _FakeRequest
        files = get_viirs_sdr_20170128_1229(base_dir=str(tmpdir),
                                            channels=("I01", "M01"))
        assert len(files) == 10 * (1 + 1 + 2)  # 10 granules * (1 I band + 1 M band + 2 geolocation)
        self._assert_bands_in_filenames_and_contents(("SVI01", "SVM01", "GITCO", "GMTCO"), files, 10)

        get_mock = mock.MagicMock()
        _requests.get.return_value = get_mock
        files = get_viirs_sdr_20170128_1229(base_dir=str(tmpdir),
                                            channels=("I01", "M01"),
                                            granules=(2, 3))
        assert len(files) == 2 * (1 + 1 + 2)  # 2 granules * (1 I band + 1 M band + 2 geolocation)
        get_mock.assert_not_called()
        self._assert_bands_in_filenames_and_contents(("SVI01", "SVM01", "GITCO", "GMTCO"), files, 2)

    @mock.patch('satpy.demo.viirs_sdr.requests')
    def test_download_channels_num_granules_dnb(self, _requests, tmpdir):
        """Test downloading and re-downloading VIIRS SDR DNB data with select granules."""
        from satpy.demo import get_viirs_sdr_20170128_1229
        _requests.get.side_effect = _FakeRequest
        files = get_viirs_sdr_20170128_1229(base_dir=str(tmpdir),
                                            channels=("DNB",),
                                            granules=(5, 6, 7, 8, 9))
        assert len(files) == 5 * (1 + 1)  # 5 granules * (1 DNB + 1 geolocation)
        self._assert_bands_in_filenames_and_contents(("SVDNB", "GDNBO"), files, 5)

    def _assert_bands_in_filenames_and_contents(self, band_prefixes, filenames, num_files_per_band):
        self._assert_bands_in_filenames(band_prefixes, filenames, num_files_per_band)
        self._assert_file_contents(filenames)

    @staticmethod
    def _assert_bands_in_filenames(band_prefixes, filenames, num_files_per_band):
        for band_name in band_prefixes:
            files_for_band = [x for x in filenames if band_name in x]
            assert files_for_band
            assert len(set(files_for_band)) == num_files_per_band

    @staticmethod
    def _assert_file_contents(filenames):
        for fn in filenames:
            with open(fn, "rb") as fake_hdf5_file:
                assert fake_hdf5_file.read().decode("ascii") == os.path.basename(fn)
