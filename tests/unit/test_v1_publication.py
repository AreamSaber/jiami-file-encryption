import concurrent.futures
import errno
import os
from pathlib import Path
import threading

import pytest

from src.package_format import publication as pub


def stage_for(destination):
    stage=pub.make_stage(destination)
    pub.write_private(stage/'data',b'complete-data')
    pub.write_private(stage/'secret',b'complete-secret')
    return stage


def validate(stage):
    assert (stage/'data').read_bytes()==b'complete-data'
    assert (stage/'secret').read_bytes()==b'complete-secret'


@pytest.mark.parametrize('kind',['file','empty_directory','directory'])
def test_existing_destination_is_untouched(tmp_path,kind):
    dest=tmp_path/'final';stage=stage_for(dest)
    if kind=='file': dest.write_bytes(b'original')
    else:
        dest.mkdir()
        if kind=='directory':(dest/'original').write_bytes(b'original')
    with pytest.raises(OSError):pub.publish_directory(stage,dest,validate)
    validate(stage)
    if kind=='file':assert dest.read_bytes()==b'original'
    elif kind=='directory':assert (dest/'original').read_bytes()==b'original'
    else:assert not list(dest.iterdir())


def test_competing_publishers_have_one_winner(tmp_path):
    dest=tmp_path/'final';stages=[stage_for(dest),stage_for(dest)];barrier=threading.Barrier(2)
    def publish(stage):
        barrier.wait()
        try:pub.publish_directory(stage,dest,validate);return True
        except FileExistsError:return False
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results=list(pool.map(publish,stages))
    assert sum(results)==1
    validate(dest)
    validate(stages[results.index(False)])


def test_pre_rename_failure_never_creates_destination(tmp_path,monkeypatch):
    dest=tmp_path/'final';stage=stage_for(dest)
    def fail(*args):raise OSError('injected before rename')
    monkeypatch.setattr(pub,'rename_noreplace',fail)
    with pytest.raises(OSError):pub.publish_directory(stage,dest,validate)
    assert not dest.exists();validate(stage)


def test_parent_dot_segments_do_not_report_cross_device(tmp_path):
    (tmp_path/'child').mkdir()
    dest = tmp_path/'child'/'..'/'final'
    stage = stage_for(dest)
    result = pub.publish_directory(stage, dest, validate)
    assert result.path == tmp_path/'final'
    validate(result.path)


@pytest.mark.skipif(os.name=='nt',reason='Linux directory synchronization contract')
def test_directory_sync_order_and_post_commit_failure(tmp_path,monkeypatch):
    dest=tmp_path/'final';stage=stage_for(dest);events=[]
    actual=pub.rename_noreplace
    def rename(src,dst):events.append('rename');actual(src,dst)
    def sync(path):
        events.append(Path(path))
        if 'rename' in events:raise OSError('injected post-commit sync failure')
    monkeypatch.setattr(pub,'rename_noreplace',rename);monkeypatch.setattr(pub,'sync_directory',sync)
    result=pub.publish_directory(stage,dest,validate)
    assert events==[stage,tmp_path,'rename',tmp_path]
    assert result.durability=='unconfirmed' and 'Published' in result.warning
    validate(dest);assert not stage.exists()


@pytest.mark.skipif(os.name=='nt',reason='Linux native no-replace error handling')
@pytest.mark.parametrize('code',[errno.ENOSYS,errno.EINVAL,errno.EXDEV])
def test_native_failure_never_falls_back(tmp_path,monkeypatch,code):
    dest=tmp_path/'final';stage=stage_for(dest)
    class Native:
        def __call__(self,*args):return -1
    class Lib:
        renameat2=Native()
    monkeypatch.setattr(pub.ctypes,'CDLL',lambda *a,**k:Lib())
    monkeypatch.setattr(pub.ctypes,'get_errno',lambda:code)
    monkeypatch.setattr(pub.os,'replace',lambda *a:pytest.fail('must not overwrite'))
    with pytest.raises(OSError):pub.publish_directory(stage,dest,validate)
    assert not dest.exists();validate(stage)
