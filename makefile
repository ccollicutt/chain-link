ifndef CHAIN_LINK_IMAGE_TAG
$(error CHAIN_LINK_IMAGE_TAG is not set)
endif

image:
	docker build -t chain-link .

push-image:
	docker tag chain-link $(CHAIN_LINK_IMAGE_TAG)
	docker push $(CHAIN_LINK_IMAGE_TAG)

image-all:
	@$(MAKE) image
	@$(MAKE) push-image
