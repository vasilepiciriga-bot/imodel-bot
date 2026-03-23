package queue

import (
	"context"

	"github.com/hibiken/asynq"
)

type QueuesInfo struct {
	Queues map[string]int `json:"queues"`
}

func SnapshotQueues(ctx context.Context, ins *asynq.Inspector) QueuesInfo {
	out := QueuesInfo{Queues: map[string]int{}}
	if ins == nil { return out }
	names, _ := ins.Queues()
	for _, q := range names {
		n, _ := ins.Stats(q)
		if n != nil { out.Queues[q] = n.Pending }
	}
	return out
}
