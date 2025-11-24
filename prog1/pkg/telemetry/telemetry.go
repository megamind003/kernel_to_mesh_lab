package telemetry

import (
	"fmt"
	"sync"
	"time"
)

type EventType string

const (
	EventContainerStarted EventType = "ContainerStarted"
	EventContainerStopped EventType = "ContainerStopped"
	EventResourceOOM      EventType = "ResourceOOM"
	EventNodeJoined       EventType = "NodeJoined"
)

type Event struct {
	Type      EventType
	Timestamp time.Time
	Source    string // e.g., "node-1", "container-xyz"
	Data      map[string]interface{}
}

type EventBus struct {
	subscribers []chan Event
	mu          sync.RWMutex
}

var globalBus *EventBus
var once sync.Once

func GetBus() *EventBus {
	once.Do(func() {
		globalBus = &EventBus{}
	})
	return globalBus
}

func (eb *EventBus) Subscribe() <-chan Event {
	eb.mu.Lock()
	defer eb.mu.Unlock()
	ch := make(chan Event, 100)
	eb.subscribers = append(eb.subscribers, ch)
	return ch
}

func (eb *EventBus) Publish(evt Event) {
	eb.mu.RLock()
	defer eb.mu.RUnlock()
	if evt.Timestamp.IsZero() {
		evt.Timestamp = time.Now()
	}
	for _, ch := range eb.subscribers {
		select {
		case ch <- evt:
		default:
			// Drop event if subscriber is slow
			fmt.Println("Warning: Dropped event, subscriber slow")
		}
	}
}

func Emit(eventType EventType, source string, data map[string]interface{}) {
	GetBus().Publish(Event{
		Type:   eventType,
		Source: source,
		Data:   data,
	})
}
