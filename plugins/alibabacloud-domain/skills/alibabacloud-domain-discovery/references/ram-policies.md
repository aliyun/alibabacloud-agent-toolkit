# RAM permissions

Public availability, reference-price, WHOIS, and domain-knowledge routes normally require no account RAM action. Do not request account-wide permissions for this Skill.

## required_permissions

No Alibaba Cloud RAM action is declared for the public routes in the current reference implementation.

If the service returns an exact `AccessDeniedDetail.AuthAction`, verify that the selected route is still read-only and update this document before recommending that action. Never recommend a wildcard action.
