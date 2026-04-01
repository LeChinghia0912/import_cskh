<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class CskhTicketAttachment extends Model
{
    protected $connection = 'mysql4';

    protected $table = 'cskh_ticket_attachments';

    public $timestamps = false;

    protected $fillable = [
        'cskh_ticket_id',
        'image_array',
        'video_ticket',
    ];

    protected $casts = [
        'image_array' => 'array',
    ];

    public function ticket(): BelongsTo
    {
        return $this->belongsTo(CskhTicket::class, 'cskh_ticket_id');
    }
}
