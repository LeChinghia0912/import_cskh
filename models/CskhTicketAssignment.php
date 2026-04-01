<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class CskhTicketAssignment extends Model
{
    protected $connection = 'mysql4';

    protected $table = 'cskh_ticket_assignments';

    public $timestamps = false;

    protected $fillable = [
        'ticket_id',
        'assigned_to',
        'assigned_by',
        'assigned_at',
        'unassigned_at',
    ];

    protected $casts = [
        'assigned_at' => 'datetime',
        'unassigned_at' => 'datetime',
    ];

    public function ticket(): BelongsTo
    {
        return $this->belongsTo(CskhTicket::class, 'ticket_id');
    }

    public function assignee(): BelongsTo
    {
        return $this->belongsTo(User::class, 'assigned_to');
    }

    public function assignedBy(): BelongsTo
    {
        return $this->belongsTo(User::class, 'assigned_by');
    }
}

