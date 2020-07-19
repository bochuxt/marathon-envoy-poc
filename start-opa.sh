#!/bin/bash
#docker run -v $PWD/opa:/example openpolicyagent/opa eval  /example/policy.rego 'data.example.greeting'
#opa eval <query> [flags]
docker run -v $PWD/opa:/example openpolicyagent/opa eval -d /example 'data.example.greeting'
#docker run -p 8181:8181 -v $PWD/opa:/example  openpolicyagent/opa run --server --log-level debug