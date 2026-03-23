package queue

import (
    "context"
    "github.com/hibiken/asynq"
)

type DLQItem struct {
    Queue string `json:"queue"`
    ID    string `json:"id"`
    Type  string `json:"type"`
    Error string `json:"error"`
}

type DLQList struct {
    Items []DLQItem `json:"items"`
}

func SnapshotDLQ(ctx context.Context, ins *asynq.Inspector) DLQList {
    out := DLQList{Items: []DLQItem{}}
    if ins == nil { return out }
    queues, _ := ins.Queues()
    for _, q := range queues {
        tasks, _ := ins.ListDeadTasks(q, asynq.PageSize(50), asynq.Page(1))
        for _, t := range tasks {
            out.Items = append(out.Items, DLQItem{Queue: q, ID: t.ID, Type: t.Type, Error: t.LastErr})
        }
    }
    return out
}

func RequeueTask(ctx context.Context, ins *asynq.Inspector, queue, id string) error {
    if ins == nil { return nil }
    return ins.RequeueDeadTask(queue, id)
}

