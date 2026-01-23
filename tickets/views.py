from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
from .models import Ticket, TicketComment
from .forms import TicketForm, TicketCommentForm
from django.db.models import Q

# Create your views here.

class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'tickets/ticket_list.html'
    context_object_name = 'tickets'
    ordering = ['-created_at']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # 1. Superuser / Manager / Admin -> See All
        if user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager']).exists():
            # Sorting Logic (preserved)
            sort_by = self.request.GET.get('sort', '-created_at')
            direction = self.request.GET.get('order', 'desc')
            
            # Mapping frontend sort keys to model fields
            sort_mapping = {
                'id': 'id',
                'topic': 'topic__name',
                'title': 'title',
                'requester': 'created_by__first_name',
                'priority': 'priority',
                'status': 'status',
                'created': 'created_at'
            }
            
            db_field = sort_mapping.get(sort_by, '-created_at')
            
            if direction == 'desc' and not db_field.startswith('-'):
                db_field = f'-{db_field}'
            elif direction == 'asc' and db_field.startswith('-'):
                db_field = db_field[1:]
                
            return queryset.order_by(db_field)

        # 2. IT Support -> Scoped Visibility
        if user.groups.filter(name='IT Support').exists():
            if hasattr(user, 'location') and user.location:
                # Hierarchical Filter
                descendants = user.location.get_descendants(include_self=True)
                descendant_ids = [loc.id for loc in descendants]
                
                queryset = queryset.filter(
                    Q(asset__location_id__in=descendant_ids) |
                    Q(created_by__location_id__in=descendant_ids) |
                    Q(assigned_to=user) |
                    Q(created_by=user)
                ).distinct()
            else:
                # Fallback if no location assigned
                queryset = queryset.filter(Q(assigned_to=user) | Q(created_by=user))
        
        # 3. Standard User -> Own Tickets Only
        else:
            queryset = queryset.filter(created_by=user)
            
        # Sorting Logic (Re-apply for filtered qs)
        sort_by = self.request.GET.get('sort', '-created_at')
        direction = self.request.GET.get('order', 'desc')
        
        sort_mapping = {
            'id': 'id',
            'topic': 'topic__name',
            'title': 'title',
            'requester': 'created_by__first_name',
            'priority': 'priority',
            'status': 'status',
            'created': 'created_at'
        }
        
        db_field = sort_mapping.get(sort_by, '-created_at')
        
        if direction == 'desc' and not db_field.startswith('-'):
            db_field = f'-{db_field}'
        elif direction == 'asc' and db_field.startswith('-'):
            db_field = db_field[1:]
            
        return queryset.order_by(db_field)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_sort'] = self.request.GET.get('sort', 'created')
        context['current_order'] = self.request.GET.get('order', 'desc')
        return context

class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'tickets/ticket_form.html'
    success_url = reverse_lazy('ticket_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Ticket created successfully!")
        return super().form_valid(form)

class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'tickets/ticket_detail.html'
    context_object_name = 'ticket'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment_form'] = TicketCommentForm()
        # Helper bools for template
        user = self.request.user
        context['is_it_support'] = user.is_superuser or user.groups.filter(name='IT Support').exists()
        context['is_manager'] = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager']).exists()
        
        if context['is_manager']:
             from django.contrib.auth import get_user_model
             User = get_user_model()
             context['it_staff'] = User.objects.filter(groups__name='IT Support')
             
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # 1. Handle Status Actions (Resolve/Close)
        if 'status_action' in request.POST:
            # Check permissions
            is_it = request.user.is_superuser or request.user.groups.filter(name='IT Support').exists()
            if is_it:
                action = request.POST.get('status_action')
                if action == 'self_assign':
                    self.object.assigned_to = request.user
                    if self.object.status == 'Open':
                        self.object.status = 'Assigned'
                    messages.success(request, f"You have taken ownership of this ticket.")
                elif action == 'resolve':
                    self.object.status = 'Resolved'
                    self.object.resolved_at = timezone.now()
                    messages.success(request, "Ticket marked as Resolved.")
                elif action == 'close':
                    self.object.status = 'Closed'
                    self.object.closed_at = timezone.now()
                    messages.success(request, "Ticket closed.")
                elif action == 'reopen':
                    self.object.status = 'Open'
                    # Clear resolution dates if reopening? Optional.
                    messages.info(request, "Ticket re-opened.")
                elif action == 'assign':
                     user_id = request.POST.get('assigned_to')
                     if user_id:
                         from django.contrib.auth import get_user_model
                         User = get_user_model()
                         assignee = get_object_or_404(User, pk=user_id)
                         self.object.assigned_to = assignee
                         self.object.status = 'Assigned'
                         messages.success(request, f"Ticket assigned to {assignee.username}.")
                
                self.object.save()
                return redirect('ticket_detail', pk=self.object.pk)
            else:
                 messages.error(request, "You do not have permission to perform this action.")

        # 2. Handle Comments
        form = TicketCommentForm(request.POST, request.FILES)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.ticket = self.object
            comment.user = request.user
            comment.save()
            messages.success(request, "Reply posted.")
            return redirect('ticket_detail', pk=self.object.pk)
        
        context = self.get_context_data(object=self.object)
        context['comment_form'] = form
        return self.render_to_response(context)
