from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Book, MemberProfile, LibrarySettings, User
from django.apps import apps
from django.db.models.signals import post_migrate
from django.contrib.auth.models import Group




@receiver(post_save, sender=Book)
def generate_rack_no(sender, instance, created, **kwargs):
    if created and instance.rack_no == '1':
        settings = LibrarySettings.objects.first()
        if settings and '-' in settings.rack_number_format:
            prefix, padding = settings.rack_number_format.split('-')
            padded_number = str(instance.id).zfill(len(padding))
            instance.rack_no = f"{prefix}-{padded_number}"
            instance.save()


@receiver(post_save, sender=MemberProfile)
def generate_member_id(sender, instance, created, **kwargs):
    if created and instance.member_id == 'unknown':
        settings = LibrarySettings.objects.first()
        if settings and '-' in settings.member_id_format:
            parts = settings.member_id_format.split('-')
            prefix = '-'.join(parts[:-1])
            padding = parts[-1]
            padded_number = str(instance.id).zfill(len(padding))
            instance.member_id = f"{prefix}-{padded_number}"
            instance.save()


@receiver(post_save, sender=User)
def assign_group_on_role_change(sender, instance, **kwargs):
    """
    After a User is saved, sync their Django groups:
     • If instance.role matches one of User.Role.choices, use that.
     • Otherwise (or if they have no group yet), default to MEMBER.
     • Create the Group if it doesn't exist.
    """
    # all possible role names from your TextChoices
    role_names = [r for r, _ in User.Role.choices]

    # clear out any old role-groups
    instance.groups.remove(*Group.objects.filter(name__in=role_names))

    # pick which group to assign
    if instance.role in role_names:
        group_name = instance.role
    else:
        # no valid role chosen → default to MEMBER
        group_name = User.Role.MEMBER

    # get or create that group
    grp, _ = Group.objects.get_or_create(name=group_name)

    # add the user to it
    instance.groups.add(grp)


@receiver(post_migrate)
def ensure_role_groups(sender, **kwargs):
    User = apps.get_model('core', 'User')
    for role_value, _ in User.Role.choices:
        Group.objects.get_or_create(name=role_value)