package example

greeting = msg {
    info := opa.runtime()
    hostname := info.env["HOSTNAME"]
    msg := sprintf(" hello from container %q!", [hostname])
}