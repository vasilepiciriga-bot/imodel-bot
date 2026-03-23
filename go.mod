module imodel-bot

go 1.22

require (
	github.com/aws/aws-sdk-go-v2 v1.30.0
	github.com/aws/aws-sdk-go-v2/config v1.27.16
	github.com/aws/aws-sdk-go-v2/feature/s3/manager v1.17.15
	github.com/aws/aws-sdk-go-v2/service/s3 v1.55.1
	github.com/gofiber/fiber/v2 v2.52.0
	github.com/hibiken/asynq v0.27.5
	github.com/jackc/pgx/v5 v5.6.0
	github.com/openai/openai-go v0.3.0
	github.com/redis/go-redis/v9 v9.6.1
	gopkg.in/telebot.v3 v3.2.1
)

replace github.com/openai/openai-go => github.com/openai/openai-go v0.3.0
