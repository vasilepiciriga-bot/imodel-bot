package domain

// SubPlan describes a subscription tier.
type SubPlan struct {
	Key         string
	Label       string
	Stars       int // per month
	Credits     int // added on each billing cycle; -1 = unlimited
	Description string
	QueuePro    bool // routes to priority queue
}

var SubPlans = []SubPlan{
	{
		Key:         "basic",
		Label:       "⭐ Basic",
		Stars:       400,
		Credits:     30,
		Description: "30 generations/month, all presets",
		QueuePro:    false,
	},
	{
		Key:         "pro",
		Label:       "💎 Pro",
		Stars:       900,
		Credits:     100,
		Description: "100 generations/month, priority queue, Copy mode",
		QueuePro:    true,
	},
	{
		Key:         "unlimited",
		Label:       "🚀 Unlimited",
		Stars:       2000,
		Credits:     -1,
		Description: "Unlimited generations, priority queue, all features",
		QueuePro:    true,
	},
}

func FindSubPlan(key string) *SubPlan {
	for i := range SubPlans {
		if SubPlans[i].Key == key {
			return &SubPlans[i]
		}
	}
	return nil
}
