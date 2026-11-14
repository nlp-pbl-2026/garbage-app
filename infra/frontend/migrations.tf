# Preserve previously managed Actions resources when opting in on older states.
moved {
  from = aws_iam_role.deploy
  to   = aws_iam_role.deploy[0]
}
moved {
  from = aws_iam_role_policy.deploy
  to   = aws_iam_role_policy.deploy[0]
}
