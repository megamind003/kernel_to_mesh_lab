package storage

/*
#cgo LDFLAGS: -L../../libhydra/target/release -lhydra_engine
#include <stdlib.h>

int hydra_open(const char* path);
int hydra_put(const char* key, const char* val, int val_len);
int hydra_get(const char* key, char* val_out, int max_len);
int hydra_close();
*/
import "C"
import (
	"errors"
	"unsafe"
)

type RustEngine struct {
	path string
}

func NewRustEngine(path string) (*RustEngine, error) {
	cPath := C.CString(path)
	defer C.free(unsafe.Pointer(cPath))

	ret := C.hydra_open(cPath)
	if ret != 0 {
		return nil, errors.New("failed to open hydra engine")
	}

	return &RustEngine{path: path}, nil
}

func (e *RustEngine) Put(key string, value []byte) error {
	cKey := C.CString(key)
	defer C.free(unsafe.Pointer(cKey))
	
	// We need to be careful with empty values or nil pointers if that's allowed
	cVal := C.CString(string(value)) // This copies, but it's safe. For zero-copy we'd use unsafe.Pointer
	defer C.free(unsafe.Pointer(cVal))

	ret := C.hydra_put(cKey, cVal, C.int(len(value)))
	if ret != 0 {
		return errors.New("failed to put key")
	}
	return nil
}

func (e *RustEngine) Get(key string) ([]byte, error) {
	cKey := C.CString(key)
	defer C.free(unsafe.Pointer(cKey))

	// Allocate a buffer for the value
	// TODO: Handle larger values dynamically or via a two-step call (get size then get data)
	maxLen := 1024 * 1024 // 1MB buffer
	buf := make([]byte, maxLen)
	
	ret := C.hydra_get(cKey, (*C.char)(unsafe.Pointer(&buf[0])), C.int(maxLen))
	
	if ret == -4 {
		return nil, errors.New("key not found")
	} else if ret < 0 {
		return nil, errors.New("error getting key")
	}

	return buf[:ret], nil
}

func (e *RustEngine) Close() error {
	ret := C.hydra_close()
	if ret != 0 {
		return errors.New("failed to close engine")
	}
	return nil
}
