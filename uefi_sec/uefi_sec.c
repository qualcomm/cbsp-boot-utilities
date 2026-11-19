/*
 * Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
 * SPDX-License-Identifier: BSD-3-Clause-Clear
 */

/*
 * Uefisec Application:
 * Uefisec Application to update UEFI Secure variable to RPMB storage
 * partition.
 *
 * Description:
 * This application periodically updates UEFI Secure variables to RPMB
 * storage partition by communicating with Trusted Appplication(TA) which
 * is running in TZ. 
 *
 * Usage:
 * uefisec
 * *********************************************************
 */

#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <unistd.h>
#include <dirent.h>
#include <fcntl.h>
#include <pthread.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <sys/eventfd.h>
#include <errno.h>
#include <BufferAllocator/BufferAllocatorWrapper.h>
#include <dirent.h>

#define ION_BIT(nr)                     (1U << (nr))
#define ION_QSECOM_HEAP_ID              ION_BIT(7)

#include "QSEEComAPI.h"
#include <sys/mman.h>
#include <getopt.h>
#include <dlfcn.h>

#include <log.h>
#ifdef LOG_TAG
#undef LOG_TAG
#endif
#define LOG_TAG "UEFISEC: "

#define NON_LEGACY_CMD_LINE_ARGS 1
#define RUN_TESTS 0
#define ION_BUFFER_LENGTH (20)

/* Error code: status sent as response to command from sample client*/

#define SUCCESS 0
#define FAILED -1

#ifdef OE
#include <syslog.h>
#define LOGI(...) syslog(LOG_NOTICE, "INFO:" __VA_ARGS__)
#define LOGV(...) syslog(LOG_NOTICE,"VERB:" __VA_ARGS__)
#define LOGD(...) syslog(LOG_DEBUG,"DBG:" __VA_ARGS__)
#define LOGE(...) syslog(LOG_ERR,"ERR:" __VA_ARGS__)
#define LOGW(...) syslog(LOG_WARNING,"WRN:" __VA_ARGS__)
#define strlcat(d,s,l) snprintf(d+strlen(d),l,"%s",s)
#endif

#define MAX_APP_NAME 25
#define MAX_FNAME		MAX_APP_NAME
#define MAX_FNAME_EXT		4
#define MAX_PATH_NAME		80
#define UNUSED(x)		(x)

#define TABLE_ID_RESERVED 0
#define SERVICE_UEFI_VAR_SYNC_VAR_TABLES 0x000800B
#define TA_NAME "qcom.tz.uefisecapp"

struct qsc_ion_info {
	int32_t ion_fd;
	int32_t ifd_data_fd;
	unsigned char * ion_sbuffer;
	uint32_t sbuf_len;
};

typedef struct
{
  uint32_t             cmd_id;
  uint32_t             len;
  uint32_t             table_id;
} TZ_SVC_REQ_VAR_SYNC_VAR_TABLES;

typedef struct
{
  uint32_t             cmd_id;
  uint32_t             len;
  uint32_t             status;
} TZ_SVC_RSP_VAR_SYNC_VAR_TABLES;

/* load whole img: *.mbn or split image "*.mdt + *.b01 +*.b02 + ..." */
static int load_whole_mbn = 0;

static int32_t qsc_ION_memalloc(struct qsc_ion_info *handle,
				uint32_t size)
{
    int32_t buffer_fd = -1, ret = -1;
    struct dma_buf_sync buf_sync;
    unsigned char *v_addr = NULL;
    uint32_t len = (size + 4095) & (~4095);

    BufferAllocator* bufferAllocator = CreateDmabufHeapBufferAllocator();
    if (bufferAllocator == NULL) {
        LOGE("CreateDmabufHeapBufferAllocator() failed.\n");
        goto alloc_fail;
    }

    buffer_fd = DmabufHeapAlloc(bufferAllocator, "qcom,qseecom", len, 0, 0);

    if (buffer_fd < 0) {
        LOGE("Error: DMA-Buf allocation failed from heap %d, len %d, errno = %d\n",
                                                       ION_QSECOM_HEAP_ID, len, errno);
        goto alloc_fail;
    }
    v_addr = (unsigned char *)mmap(NULL, len, PROT_READ | PROT_WRITE,
                                             MAP_SHARED, buffer_fd, 0);
    if (v_addr == MAP_FAILED) {
        LOGE("Error: MMAP failed: heap %d, len %d, errno = %d\n",
                                                 ION_QSECOM_HEAP_ID, len, errno);
        goto map_fail;
    }

    handle->ion_fd = -1; /* ion_fd not needed any more */
    handle->ifd_data_fd = buffer_fd;
    handle->ion_sbuffer = v_addr;
    handle->sbuf_len = size;

    buf_sync.flags = DMA_BUF_SYNC_START | DMA_BUF_SYNC_RW;
    ret = ioctl(buffer_fd, DMA_BUF_IOCTL_SYNC, &buf_sync);
    if (ret) {
        LOGE("Error: DMA_BUF_IOCTL_SYNC start failed, ret = %d, errno = %d\n",
			                                           ret, errno);
        goto sync_fail;
    }
    FreeDmabufHeapBufferAllocator(bufferAllocator);
    return ret;

sync_fail:
    if (v_addr) {
        munmap(v_addr, len);
        handle->ion_sbuffer = NULL;
    }
map_fail:
    if (handle->ifd_data_fd >=0)
        close(handle->ifd_data_fd);
alloc_fail:
    handle->ifd_data_fd = -1;
    FreeDmabufHeapBufferAllocator(bufferAllocator);
    return ret;
}

static int qsc_ion_dealloc(struct qsc_ion_info *handle)
{
	struct dma_buf_sync buf_sync;
	uint32_t len = (handle->sbuf_len + 4095) & (~4095);
	int ret = 0;

	buf_sync.flags = DMA_BUF_SYNC_END | DMA_BUF_SYNC_RW;
	ret = ioctl(handle->ifd_data_fd, DMA_BUF_IOCTL_SYNC, &buf_sync);
	if (ret) {
		LOGE("Error:: DMA_BUF_IOCTL_SYNC start failed, ret = %d, errno = %d\n",
				ret, errno);
	}

	if (handle->ion_sbuffer) {
		munmap(handle->ion_sbuffer, len);
		handle->ion_sbuffer = NULL;
	}
	if (handle->ifd_data_fd >= 0 ) {
		close(handle->ifd_data_fd);
		handle->ifd_data_fd= -1;
	}
	if (handle->ion_fd >= 0 ) {
		close(handle->ion_fd);
		handle->ion_fd = -1;
	}
	return ret;
}


int32_t qsc_start_app_V2(struct QSEECom_handle **l_QSEEComHandle,
				const char *path, const char *appname, int32_t sb_length)
{
	unsigned long f_size = 0;
	char temp_fname[MAX_PATH_NAME + MAX_FNAME + MAX_FNAME_EXT] = {0}; /* local fname */
	int32_t fd = 0;
	struct stat f_info;
	unsigned char *trustlet_buf = NULL;
	int32_t ret = 0;

	/* Parse the ELF */
	if (!path || !appname) {
		LOGE("path or fname is NULL");
		ret = -1;
		goto exit;
	}
	if ((strnlen(path, MAX_PATH_NAME) +
		strnlen(appname, MAX_FNAME) +
		MAX_FNAME_EXT + 2) >= sizeof(temp_fname))
	{
		LOGE("length of path, fname and ext is too long (>%zu)",sizeof(temp_fname));
		ret = -1;
		goto exit;
	}
	snprintf(temp_fname, sizeof(temp_fname), "%s/%s.mbn", path, appname);
	fd = open(temp_fname, O_RDONLY);
	if (fd  == -1) {
		LOGE("Cannot open file %s/%s.mbn, errno = %d", path, appname, errno);
		printf("Cannot open file %s/%s.mbn, errno = %d\n", path, appname, errno);
		ret = -1;
		goto exit;
	}
	LOGW("Succeed to open file %s/%s.mbn", path, appname);
	printf("Succeed to open file %s/%s.mbn\n", path, appname);

	/* Grab the file size information */
	if (fstat(fd, &f_info) == -1) {
		LOGE("fstat failed, errno = %d", errno);
		printf("fstat failed, errno = %d\n", errno);
		ret = -1;
		goto exit_close;
	}
	trustlet_buf = (unsigned char *)malloc(f_info.st_size);
	if (!trustlet_buf) {
		LOGE("Malloc failed with size %d", (int)f_info.st_size);
		printf("Malloc failed with size %d\n", (int)f_info.st_size);
		ret = -1;
		goto exit_close;
	}
	/* Read the file contents starting at into buffer */
	ret = read(fd, trustlet_buf, f_info.st_size);
	if (ret == -1) {
		LOGE("Error::reading from image %s.mbn failed.\n", appname);
		printf("Error::reading from image %s.mbn failed\n", appname);
		ret = -1;
		goto exit_free;
	}
	/* Call QSEECom_start_app_v2 */
	ret = QSEECom_start_app_V2(l_QSEEComHandle, appname, trustlet_buf, f_info.st_size,
				sb_length);

exit_free:
	free(trustlet_buf);
exit_close:
	close(fd);
exit:
	return ret;
}

int32_t start_app_from_target_dir(struct QSEECom_handle **l_QSEEComHandle,
				const char* root_path, const char *appname, int32_t buf_size)
{
	int32_t ret = 0;
	struct dirent *entry = NULL;
	char app_path[1024] = {0};

	DIR *dir = opendir(root_path);
	if (!dir) {
		LOGE("Error opening directory");
		return -1;
	}

	while ((entry = readdir(dir)) != NULL) {
		if (entry->d_type == DT_DIR) {
			// Skip "." and ".." directories
			if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0)
			continue;

			snprintf(app_path, sizeof(app_path), "%s/%s", root_path, entry->d_name);
			printf("%s: app_path to check: %s\n",__func__,app_path);
			ret = QSEECom_start_app(l_QSEEComHandle, app_path,
					appname, buf_size);
			if (!ret)
				break;
		}
	}

	return ret;
}


/**@brief:  Implement simple application start
 *
 * @param[in/out]	handle.
 * @param[in]		appname.
 * @param[in]		buffer size.
 * @return	zero on success or error count on failure.
 */
int32_t qsc_start_app(struct QSEECom_handle **l_QSEEComHandle,
                        const char *appname, int32_t buf_size)
{
	int32_t ret = 0;

	/* start the application */
	if (!load_whole_mbn) {
		/* load split images */
		ret = start_app_from_target_dir(l_QSEEComHandle, "/lib/firmware/qcom",
						appname, buf_size);
		if (ret)
			ret = QSEECom_start_app(l_QSEEComHandle, "/vendor/firmware_mnt/image",
					appname, buf_size);
		if (ret)
			ret = QSEECom_start_app(l_QSEEComHandle, "/firmware/image",
					appname, buf_size);
		if (ret)
			ret = QSEECom_start_app(l_QSEEComHandle, "/home/root",
					appname, buf_size);
	} else {
		/* load whole image */
		ret = start_app_from_target_dir(l_QSEEComHandle, "/lib/firmware/qcom",
						appname, buf_size);
		if (ret)
			ret = qsc_start_app_V2(l_QSEEComHandle, "/vendor/firmware_mnt/image",
				appname, buf_size);
		if (ret)
			ret = qsc_start_app_V2(l_QSEEComHandle, "/firmware/image",
				appname, buf_size);
		if (ret)
			ret = qsc_start_app_V2(l_QSEEComHandle, "/home/root",
				appname, buf_size);
	}
	if (ret) {
	   LOGE("Loading app -%s failed",appname);
	   printf("%s: Loading app -%s failed\n",__func__,appname);
	} else {
	   LOGD("Loading app -%s succeded",appname);
	}
	return ret;
}

/**@brief:  Implement simple shutdown app
 * @param[in]	handle.
 * @return	zero on success or error count on failure.
 */
int32_t qsc_shutdown_app(struct QSEECom_handle **l_QSEEComHandle)
{
	int32_t ret = 0;

	LOGD("qsc_shutdown_app: start");
	/* shutdown the application */
	if (*l_QSEEComHandle != NULL) {
	   ret = QSEECom_shutdown_app(l_QSEEComHandle);
	   if (ret) {
	      LOGE("Shutdown app failed with ret = %d", ret);
	      printf("%s: Shutdown app failed with ret = %d\n",__func__,ret);
	   } else {
	      LOGD("shutdown app: pass");
	   }
	} else {
		LOGE("cannot shutdown as the handle is NULL");
		printf("%s:cannot shutdown as the handle is NULL\n",__func__);
	}
	return ret;
}

int main(int argc, char *argv[])
{

    int32_t i = 0;
    int32_t j = 0;
    int32_t ret = 0;	        /* return value */
    int32_t err = 0;		/* return value */
    uint32_t req_len;
    uint32_t rsp_offset;
    uint32_t rsp_len;
    uint32_t table_id = 0;

    struct QSEECom_ion_fd_info  ion_fd_info;
    struct qsc_ion_info ihandle;
    struct QSEECom_handle *l_QSEEComHandle = NULL;
    char * verify;

    ret = qsc_start_app(&l_QSEEComHandle, TA_NAME, 1024);
    if (ret) {
      LOGE("Start uefisecapp TA: fail");
      printf("Start uefisecapp TA: fail\n");
      err++;
    }

    LOGD("send modified cmd: start");

    TZ_SVC_REQ_VAR_SYNC_VAR_TABLES *req =
      (TZ_SVC_REQ_VAR_SYNC_VAR_TABLES *) l_QSEEComHandle->ion_sbuffer;
    TZ_SVC_RSP_VAR_SYNC_VAR_TABLES *rsp = NULL;

    do {
      /* allocate 20B memory: the end of every pass frees it */
      memset(&ihandle, 0, sizeof(ihandle));
      ret = qsc_ION_memalloc(&ihandle, ION_BUFFER_LENGTH);
      if (ret) {
        LOGE("Error allocating memory in ion\n");
        return -1;
      }

      memset(&ion_fd_info, 0, sizeof(struct QSEECom_ion_fd_info));

      req->cmd_id = SERVICE_UEFI_VAR_SYNC_VAR_TABLES;
      req->table_id = TABLE_ID_RESERVED;
      req->len = ION_BUFFER_LENGTH ;
      req_len = sizeof(TZ_SVC_REQ_VAR_SYNC_VAR_TABLES);

      ion_fd_info.data[0].fd = ihandle.ifd_data_fd;
      ion_fd_info.data[0].cmd_buf_offset = sizeof(uint32_t) * 3 ;
      ion_fd_info.data[1].fd = ihandle.ifd_data_fd;
      ion_fd_info.data[1].cmd_buf_offset = sizeof(uint32_t) * 4 ;

      verify = malloc(ION_BUFFER_LENGTH);
      if(verify == NULL) {
        LOGE("Malloc failed for SEND_MODIFIED_CMD test, exiting\n");
        printf("Malloc failed for Send Modified CMD test, exiting\n");

	ret = qsc_ion_dealloc(&ihandle);
	if(ret) {
          err++;
          LOGE("return value of dealloc is %d",ret);
	  printf("return value of dealloc is %d\n",ret);
	}
        return -1;
      }

      for (j = 0; j < ION_BUFFER_LENGTH; j++) {
        *(ihandle.ion_sbuffer+j) = (char)(j%255);
	*(verify+j) = (char)(j%255);
      }

      rsp_len = sizeof(TZ_SVC_RSP_VAR_SYNC_VAR_TABLES);

      if (req_len & QSEECOM_ALIGN_MASK)
        req_len = QSEECOM_ALIGN(req_len);

      if (rsp_len & QSEECOM_ALIGN_MASK)
        rsp_len = QSEECOM_ALIGN(rsp_len);

      rsp = (TZ_SVC_RSP_VAR_SYNC_VAR_TABLES *)(l_QSEEComHandle->ion_sbuffer + req_len);
      rsp->status = 0;

      LOGD("req len = %d bytes",req_len);
      LOGD("rsp len = %d bytes",rsp_len);

      /* send request from HLOS to QSEApp */
      ret = QSEECom_send_modified_cmd(l_QSEEComHandle, req, req_len, rsp,
                                      rsp_len, &ion_fd_info);
      LOGD("rsp status = %x", rsp->status);
      if(ret) {
        err++;
	LOGD("qsc_issue_send_modified_cmd_req: fail cmd = %d ret = %d",
	      req->cmd_id, ret);
	printf("qsc_issue_send_modified_cmd_req: fail cmd = %d ret = %d\n",
		req->cmd_id, ret);
      }

      if(rsp->status < 0) {
        err++;
	LOGE("qsc_issue_send_modified_cmd_req:: failed msg_rsp->status =%d",
              rsp->status);
	printf("qsc_issue_send_modified_cmd_req:: failed msg_rsp->status =%d\n",
		rsp->status);
      }

      /* De-allocate 64KB memory */
      ret = qsc_ion_dealloc(&ihandle);
      if(ret) {
        err++;
	LOGE("return value of dealloc is %d",ret);
	printf("qsc_issue_send_modified_cmd_req::fail dealloc is %d\n",ret);
      }

      if (verify)
        free(verify);

      if (argc == 2) {
        if(atoi(argv[1]) == 1) {
	  break;
	}
      }

      sleep(600);

    } while(1);

  return err;

}
