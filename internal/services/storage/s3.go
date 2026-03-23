package storage

import (
	"bytes"
	"context"
	"fmt"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	awss3 "github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/aws/aws-sdk-go-v2/service/s3/types"
	"imodel-bot/internal/config"
)

type S3 struct {
	cli *awss3.Client
	bkt string
}

func New(cfg config.Config) *S3 {
	if cfg.S3Bucket == "" { return nil }
	lo := []func(*config.LoadOptions) error{}
	if cfg.S3Endpoint != "" {
		lo = append(lo, config.WithEndpointResolverWithOptions(aws.EndpointResolverWithOptionsFunc(
			func(service, region string, options ...interface{}) (aws.Endpoint, error) {
				return aws.Endpoint{URL: cfg.S3Endpoint, HostnameImmutable: true}, nil
			})))
	}
	awscfg, err := config.LoadDefaultConfig(context.Background(), lo...)
	if err != nil { return nil }
	cli := awss3.NewFromConfig(awscfg, func(o *awss3.Options) {
		if cfg.S3Region != "" { o.Region = cfg.S3Region }
	})
	return &S3{cli: cli, bkt: cfg.S3Bucket}
}

func (s *S3) PutBytes(ctx context.Context, key string, b []byte, contentType string) error {
	if s == nil { return nil }
	_, err := s.cli.PutObject(ctx, &awss3.PutObjectInput{
		Bucket: &s.bkt,
		Key:    &key,
		Body:   bytes.NewReader(b),
		ContentType: &contentType,
		ACL: types.ObjectCannedACLPrivate,
	})
	return err
}

func (s *S3) PresignGetURL(ctx context.Context, key string, ttl time.Duration) (string, error) {
	if s == nil { return "", fmt.Errorf("s3 not configured") }
	ps := awss3.NewPresignClient(s.cli)
	out, err := ps.PresignGetObject(ctx, &awss3.GetObjectInput{Bucket: &s.bkt, Key: &key}, awss3.WithPresignExpires(ttl))
	if err != nil { return "", err }
	return out.URL, nil
}
