# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: job_service.proto
# Protobuf Python Version: 4.25.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x11job_service.proto\x12\x0bjob_service\">\n\x13UploadResumeRequest\x12\x14\n\x0c\x66ile_content\x18\x01 \x01(\x0c\x12\x11\n\tfile_name\x18\x02 \x01(\t\"K\n\x14UploadResumeResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\x12\x11\n\tfile_path\x18\x03 \x01(\t\"5\n\x10SetApiKeyRequest\x12\x0f\n\x07\x61pi_key\x18\x01 \x01(\t\x12\x10\n\x08\x62\x61se_url\x18\x02 \x01(\t\"5\n\x11SetApiKeyResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\"F\n\x0fStartJobRequest\x12\x10\n\x08job_type\x18\x01 \x01(\t\x12\x14\n\x0c\x62rowser_type\x18\x02 \x01(\t\x12\x0b\n\x03url\x18\x03 \x01(\t\"m\n\tJobStatus\x12\x0e\n\x06status\x18\x01 \x01(\t\x12\x0f\n\x07message\x18\x02 \x01(\t\x12\x10\n\x08progress\x18\x03 \x01(\x05\x12\x13\n\x0b\x63urrent_job\x18\x04 \x01(\t\x12\x18\n\x10\x63urrent_response\x18\x05 \x01(\t\"\x10\n\x0eStopJobRequest\"I\n\x0fStopJobResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\x12\x14\n\x0c\x66inal_status\x18\x03 \x01(\t2\xbf\x02\n\nJobService\x12U\n\x0cUploadResume\x12 .job_service.UploadResumeRequest\x1a!.job_service.UploadResumeResponse\"\x00\x12L\n\tSetApiKey\x12\x1d.job_service.SetApiKeyRequest\x1a\x1e.job_service.SetApiKeyResponse\"\x00\x12\x44\n\x08StartJob\x12\x1c.job_service.StartJobRequest\x1a\x16.job_service.JobStatus\"\x00\x30\x01\x12\x46\n\x07StopJob\x12\x1b.job_service.StopJobRequest\x1a\x1c.job_service.StopJobResponse\"\x00\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'job_service_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_UPLOADRESUMEREQUEST']._serialized_start=34
  _globals['_UPLOADRESUMEREQUEST']._serialized_end=96
  _globals['_UPLOADRESUMERESPONSE']._serialized_start=98
  _globals['_UPLOADRESUMERESPONSE']._serialized_end=173
  _globals['_SETAPIKEYREQUEST']._serialized_start=175
  _globals['_SETAPIKEYREQUEST']._serialized_end=228
  _globals['_SETAPIKEYRESPONSE']._serialized_start=230
  _globals['_SETAPIKEYRESPONSE']._serialized_end=283
  _globals['_STARTJOBREQUEST']._serialized_start=285
  _globals['_STARTJOBREQUEST']._serialized_end=355
  _globals['_JOBSTATUS']._serialized_start=357
  _globals['_JOBSTATUS']._serialized_end=466
  _globals['_STOPJOBREQUEST']._serialized_start=468
  _globals['_STOPJOBREQUEST']._serialized_end=484
  _globals['_STOPJOBRESPONSE']._serialized_start=486
  _globals['_STOPJOBRESPONSE']._serialized_end=559
  _globals['_JOBSERVICE']._serialized_start=562
  _globals['_JOBSERVICE']._serialized_end=881
# @@protoc_insertion_point(module_scope)
