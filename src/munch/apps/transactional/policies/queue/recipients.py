from slimta.policy import QueuePolicy


class Clean(QueuePolicy):
    """
    Try to determine if there are multiple recipient to clean "To" header
    """
    def apply(self, envelope):
        if envelope.recipients:
            envelope.headers.replace_header('To', envelope.recipients[0])
